import os
from datetime import date, datetime

import numpy as np
import pandas as pd

import personalizacion

RUTA_CSV_EVENTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensores_bluba.csv")


FEATURES_JUGUETE = [
    "intensidad_movimiento_p90",   
    "clics_intervalo_prom_ms",     
]

K_SHRINKAGE_JUGUETE = 7   
FACTOR_Z_ALERTA = 2.0     
INTERVALO_CLIC_MIN_MS = 60  

COLUMNAS_EVENTOS = ["usuario_id", "fecha", "timestamp", "tipo", "valor"]


def _asegurar_csv_eventos():
    if not os.path.exists(RUTA_CSV_EVENTOS):
        pd.DataFrame(columns=COLUMNAS_EVENTOS).to_csv(RUTA_CSV_EVENTOS, index=False)


def registrar_evento(usuario_id: str, tipo: str, valor: float, timestamp: float = None):
    _asegurar_csv_eventos()
    ts = timestamp if timestamp is not None else datetime.now().timestamp()
    fila = {
        "usuario_id": str(usuario_id),
        "fecha": datetime.fromtimestamp(ts).date().isoformat(),
        "timestamp": ts,
        "tipo": tipo,
        "valor": valor,
    }
    df = pd.read_csv(RUTA_CSV_EVENTOS)
    df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
    df.to_csv(RUTA_CSV_EVENTOS, index=False)
    return fila


def _cargar_eventos() -> pd.DataFrame:
    _asegurar_csv_eventos()
    df = pd.read_csv(RUTA_CSV_EVENTOS)
    if df.empty:
        return df
    df["usuario_id"] = df["usuario_id"].astype(str)
    return df


def agregar_diario(df_eventos: pd.DataFrame = None) -> pd.DataFrame:
    """
    Convierte el log crudo de eventos en una fila por (usuario_id, fecha) con
    las métricas de FEATURES_JUGUETE — el mismo formato "una fila = un día"
    que usa modelo.py, para poder reutilizar personalizacion.py sin cambios.
    """
    if df_eventos is None:
        df_eventos = _cargar_eventos()
    if df_eventos.empty:
        return pd.DataFrame(columns=["usuario_id", "fecha"] + FEATURES_JUGUETE)

    filas = []
    for (usuario_id, fecha), grupo in df_eventos.groupby(["usuario_id", "fecha"]):
        mov = grupo.loc[grupo["tipo"] == "movimiento", "valor"]
        clics = grupo.loc[grupo["tipo"] == "clic"].sort_values("timestamp")

        intensidad_p90 = float(mov.quantile(0.9)) if len(mov) else np.nan

        if len(clics) >= 2:
            intervalos = clics["timestamp"].diff().dropna() * 1000  
            intervalo_prom = float(intervalos.mean())
        else:
            intervalo_prom = np.nan

        filas.append({
            "usuario_id": usuario_id,
            "fecha": fecha,
            "intensidad_movimiento_p90": intensidad_p90,
            "clics_intervalo_prom_ms": intervalo_prom,
        })

    return pd.DataFrame(filas)


def calcular_umbrales_personalizados(usuario_id: str, factor_z: float = FACTOR_Z_ALERTA) -> dict:
    df_diario = agregar_diario()

    if df_diario.empty or usuario_id not in df_diario["usuario_id"].astype(str).unique():
        return {"umbral_movimiento": 0.6, "umbral_clic_ms": 300, "dias_sesion": 0}

    baseline_df, baseline_poblacion = personalizacion.calcular_baselines(
        df_diario, FEATURES_JUGUETE, id_col="usuario_id", k_shrinkage=K_SHRINKAGE_JUGUETE
    )
    dias_sesion = personalizacion.dias_historial(baseline_df, usuario_id, id_col="usuario_id")

    if str(usuario_id) in baseline_df.index:
        media_mov = baseline_df.loc[str(usuario_id), "intensidad_movimiento_p90_media"]
        std_mov = baseline_df.loc[str(usuario_id), "intensidad_movimiento_p90_std"]
        media_clic = baseline_df.loc[str(usuario_id), "clics_intervalo_prom_ms_media"]
        std_clic = baseline_df.loc[str(usuario_id), "clics_intervalo_prom_ms_std"]
    else:
        media_mov, std_mov = baseline_poblacion["intensidad_movimiento_p90"].values()
        media_clic, std_clic = baseline_poblacion["clics_intervalo_prom_ms"].values()

    umbral_movimiento = round(float(media_mov + factor_z * std_mov), 3)
    umbral_clic_ms = int(max(media_clic - factor_z * std_clic, INTERVALO_CLIC_MIN_MS))

    return {
        "umbral_movimiento": umbral_movimiento,
        "umbral_clic_ms": umbral_clic_ms,
        "dias_sesion": dias_sesion,
    }


def resumen_diario(usuario_id: str, fecha: str = None) -> dict:
    fecha = fecha or date.today().isoformat()
    df_eventos = _cargar_eventos()
    if df_eventos.empty:
        return {"usuario_id": usuario_id, "fecha": fecha, "movimientos_bruscos": 0, "clics_rapidos": 0}

    umbrales = calcular_umbrales_personalizados(usuario_id)
    dia = df_eventos[(df_eventos["usuario_id"] == str(usuario_id)) & (df_eventos["fecha"] == fecha)]

    mov = dia.loc[dia["tipo"] == "movimiento", "valor"]
    movimientos_bruscos = int((mov > umbrales["umbral_movimiento"]).sum())

    clics = dia.loc[dia["tipo"] == "clic"].sort_values("timestamp")
    clics_rapidos = 0
    if len(clics) >= 2:
        intervalos_ms = clics["timestamp"].diff().dropna() * 1000
        clics_rapidos = int((intervalos_ms < umbrales["umbral_clic_ms"]).sum())

    return {
        "usuario_id": usuario_id,
        "fecha": fecha,
        "movimientos_bruscos": movimientos_bruscos,
        "clics_rapidos": clics_rapidos,
        "umbrales_usados": umbrales,
    }
