"""
API Flask para la propuesta Bluba.

- Recibe el micro-registro diario de la familia desde el HTML.
- Lo agrega como fila nueva a base_bluba.csv (la "base de datos").
- Entrena (o reutiliza) el modelo de modelo.py sobre esa misma base de datos
  y devuelve la predicción de crisis a 24h.

Ejecutar:
    python seed_dataset.py   # una sola vez, crea base_bluba.csv
    python app.py            # levanta la API en http://localhost:5000
"""
import os
from datetime import date

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

import modelo
import sensores
import detonantes

RUTA_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_bluba.csv")

app = Flask(__name__)
CORS(app)  # Demo: se permite cualquier origen para simplificar el front-end local.

_cache = {"modelo": None, "imputador": None, "baseline_df": None, "baseline_poblacion": None, "n_filas": -1}


def _asegurar_csv():
    if not os.path.exists(RUTA_CSV):
        raise FileNotFoundError(
            f"No se encontró {RUTA_CSV}. Ejecuta primero: python seed_dataset.py"
        )


def _obtener_modelo():
    """Reentrena si el número de filas cambió desde la última vez (dato nuevo guardado)."""
    df = modelo.cargar_datos(RUTA_CSV)
    if _cache["modelo"] is None or _cache["n_filas"] != len(df):
        m, imp, baseline_df, baseline_poblacion = modelo.entrenar_modelo(df)
        _cache.update({
            "modelo": m,
            "imputador": imp,
            "baseline_df": baseline_df,
            "baseline_poblacion": baseline_poblacion,
            "n_filas": len(df),
        })
    return _cache["modelo"], _cache["imputador"], _cache["baseline_df"], _cache["baseline_poblacion"], len(df)


@app.get("/api/salud")
def salud():
    return jsonify({"status": "ok"})


@app.post("/api/prediccion")
def prediccion():
    """
    Body JSON esperado:
    {
      "usuario_id": "familia_01",
      "horas_sueno": 6.5,               // o null si no se registró
      "calidad_sueno": 1,                // 1 mala, 2 regular, 3 buena | null
      "estado_basal": 1,                 // 1 irritable, 2 neutro, 3 tranquilo | null
      "nivel_apoyo": 2,                  // 1 alto, 2 medio, 3 bajo | null
      "salud_gi": 2,                     // 1 normal, 2 leve, 3 severo | null
      "cambio_rutina": 2,                // 0 ninguno, 1 leve, 2 drástico | null
      "desregulaciones_previas": 1,      // conteo 0-5 | null
      "alimentacion": 1,                 // no usado aún por el modelo
      "interaccion_social": 2,           // no usado aún por el modelo
      "notas": "texto libre"
    }
    """
    _asegurar_csv()
    body = request.get_json(force=True) or {}

    usuario_id = str(body.get("usuario_id") or "anonimo").strip()
    registro = {f: body.get(f) for f in modelo.FEATURES}

    modelo_rf, imputador, baseline_df, baseline_poblacion, n_historico = _obtener_modelo()
    resultado = modelo.predecir(
        registro, usuario_id, modelo_rf, imputador, baseline_df, baseline_poblacion, n_historico
    )
    # Si este usuario_id corresponde a uno de los casos reales del concurso
    # (PAC-001..004), se adjunta lo que ya sabemos de él/ella: detonantes
    # documentados y qué estrategias le han funcionado antes. Para las
    # familias sintéticas de la demo, queda en null (no hay ese historial).
    resultado["known_profile"] = detonantes.perfil_conocido(usuario_id)

    # Persistimos el registro de hoy en la base de datos CSV. La etiqueta
    # crisis_24h queda vacía porque su desenlace real aún no se conoce.
    nueva_fila = {
        "usuario_id": usuario_id,
        "fecha": date.today().isoformat(),
        **registro,
        "alimentacion": body.get("alimentacion"),
        "interaccion_social": body.get("interaccion_social"),
        "notas": body.get("notas", ""),
        "crisis_24h": "",
    }
    df = pd.read_csv(RUTA_CSV)
    df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
    df.to_csv(RUTA_CSV, index=False)

    return jsonify(resultado)


@app.get("/api/historial/<usuario_id>")
def historial(usuario_id):
    _asegurar_csv()
    df = pd.read_csv(RUTA_CSV)
    df_usuario = df[df["usuario_id"].astype(str) == str(usuario_id)].tail(10)
    return jsonify(df_usuario.to_dict(orient="records"))


@app.get("/api/detonantes/<usuario_id>")
def detonantes_conocidos(usuario_id):
    """
    Detonantes y estrategias REALES documentados para este niño/a (datos
    anonimizados del concurso), independiente de la predicción del modelo.
    Devuelve {} si no hay historial para ese usuario_id.
    """
    perfil = detonantes.perfil_conocido(usuario_id)
    return jsonify(perfil or {})


# ---------------------------------------------------------------------------
# Juguete sensorial (dado con joystick/botón vía Arduino + HC-06)
# ---------------------------------------------------------------------------
@app.post("/api/sensor/evento")
def sensor_evento():
    """
    El script puente (bridge_bluetooth.py) llama esto por cada línea que
    recibe del Arduino.
    Body: {"usuario_id": "...", "tipo": "movimiento"|"clic", "valor": number, "timestamp": number?}
    """
    body = request.get_json(force=True) or {}
    usuario_id = body.get("usuario_id")
    tipo = body.get("tipo")
    valor = body.get("valor")

    if not usuario_id or tipo not in ("movimiento", "clic") or valor is None:
        return jsonify({"error": "usuario_id, tipo ('movimiento'|'clic') y valor son obligatorios"}), 400

    fila = sensores.registrar_evento(usuario_id, tipo, float(valor), body.get("timestamp"))
    return jsonify({"ok": True, "evento": fila})


@app.get("/api/sensor/umbral/<usuario_id>")
def sensor_umbral(usuario_id):
    """
    Umbrales calibrados para ESTE niño/a. El bridge los pide al empezar una
    sesión de juego y se los baja al Arduino por Bluetooth
    (comandos "CFG,T,<umbral_movimiento>" y "CFG,D,<umbral_clic_ms>").
    """
    return jsonify(sensores.calcular_umbrales_personalizados(usuario_id))


@app.get("/api/sensor/resumen/<usuario_id>")
def sensor_resumen(usuario_id):
    """
    Resumen del día de juego: cuántos movimientos bruscos y clics rápidos
    tuvo, ya evaluados contra SU propio umbral. Pensado para pre-completar
    'desregulaciones_previas' en el registro familiar y así reducir cuánto
    tiene que tipear la familia a mano.
    """
    fecha = request.args.get("fecha")
    return jsonify(sensores.resumen_diario(usuario_id, fecha))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
