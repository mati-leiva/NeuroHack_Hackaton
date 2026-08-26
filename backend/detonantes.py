"""
Detonantes y estrategias REALES por niño/a, a partir de los datos
anonimizados entregados para el concurso (1_casos_anonimizados.csv y
5_eventos_desregulacion_tutor.csv) — NO son datos sintéticos.

Esto es deliberadamente independiente del modelo predictivo (modelo.py):
no reemplaza ninguna variable de entrenamiento ni cambia el Random
Forest. Es una capa de "lo que ya sabemos de este niño/a en particular",
que complementa la predicción con evidencia documentada en vez de
plantillas genéricas iguales para todos.

Con solo 4 casos y 7 eventos en los datos entregados, esta capa solo
tendrá contenido para esos ids (PAC-001 a PAC-004); para cualquier otro
usuario_id (p.ej. las familias sintéticas de la demo) devuelve None.

app.py importa este módulo; no se ejecuta directamente.
"""
import os

import pandas as pd

_DIR_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_RUTA_CASOS = os.path.join(_DIR_DATOS, "1_casos_anonimizados.csv")
_RUTA_EVENTOS = os.path.join(_DIR_DATOS, "5_eventos_desregulacion_tutor.csv")

RESULTADO_EXITOSO = "Regulación Exitosa"


def _cargar_casos() -> pd.DataFrame:
    if not os.path.exists(_RUTA_CASOS):
        return pd.DataFrame()
    return pd.read_csv(_RUTA_CASOS, sep=";", encoding="utf-8-sig")


def _cargar_eventos() -> pd.DataFrame:
    if not os.path.exists(_RUTA_EVENTOS):
        return pd.DataFrame()
    df = pd.read_csv(_RUTA_EVENTOS, sep=";", encoding="utf-8-sig")
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df


def perfil_conocido(usuario_id: str):
    """
    Devuelve, si existe, lo que los datos reales entregados ya documentan
    para este niño/a:
      - diagnostico / perfil_sensorial (de casos_anonimizados)
      - eventos: lista de crisis reales con su detonante, la estrategia
        usada y si funcionó (de eventos_desregulacion_tutor), más reciente
        primero
      - estrategias_efectivas: solo las que SÍ lograron regulación exitosa

    Devuelve None si usuario_id no aparece en ninguno de los dos archivos
    (caso esperado para ids que no son de este dataset del concurso).
    """
    usuario_id = str(usuario_id)
    casos = _cargar_casos()
    eventos = _cargar_eventos()

    en_casos = not casos.empty and usuario_id in casos["id_caso"].astype(str).values
    eventos_usuario = (
        eventos[eventos["id_caso"].astype(str) == usuario_id] if not eventos.empty else eventos
    )

    if not en_casos and eventos_usuario.empty:
        return None

    perfil = {"usuario_id": usuario_id}

    if en_casos:
        fila = casos[casos["id_caso"].astype(str) == usuario_id].iloc[0]
        perfil["diagnostico"] = fila["diagnostico_principal"]
        perfil["perfil_sensorial"] = fila["perfil_sensorial_predominante"]

    eventos_usuario = eventos_usuario.sort_values("fecha_hora", ascending=False)
    perfil["eventos"] = [
        {
            "fecha": fila["fecha_hora"].strftime("%Y-%m-%d %H:%M"),
            "tipo_evento": fila["tipo_evento"],
            "intensidad": fila["intensidad"],
            "detonante": fila["detonante_gatillante"],
            "estrategia": fila["estrategia_calma_aplicada"],
            "resultado": fila["resultado_estrategia"],
        }
        for _, fila in eventos_usuario.iterrows()
    ]

    exitosas = eventos_usuario[eventos_usuario["resultado_estrategia"] == RESULTADO_EXITOSO]
    perfil["estrategias_efectivas"] = exitosas["estrategia_calma_aplicada"].drop_duplicates().tolist()

    return perfil
