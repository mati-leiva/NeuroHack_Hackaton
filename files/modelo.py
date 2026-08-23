"""
Lógica de imputación (MICE) y modelo predictivo (Random Forest), adaptada de
1.py, para trabajar sobre la base de datos acumulada en base_bluba.csv.

app.py importa este módulo; no se ejecuta directamente.
"""
import numpy as np
import pandas as pd

from sklearn.experimental import enable_iterative_imputer  # noqa
from sklearn.impute import IterativeImputer
from sklearn.ensemble import RandomForestClassifier

FEATURES = [
    "horas_sueno",
    "calidad_sueno",
    "estado_basal",
    "nivel_apoyo",
    "salud_gi",
    "cambio_rutina",
    "desregulaciones_previas",
]
LABEL = "crisis_24h"

COLS_ORDINALES = [
    "calidad_sueno",
    "estado_basal",
    "nivel_apoyo",
    "salud_gi",
    "cambio_rutina",
    "desregulaciones_previas",
]

# Dirección de riesgo de cada variable (según la fórmula de 1.py):
# "bajo"  -> valores bajos aumentan el riesgo (p.ej. dormir pocas horas)
# "alto"  -> valores altos aumentan el riesgo (p.ej. malestar GI severo)
# "neutro"-> no forma parte de la fórmula de riesgo original
DIRECCION_RIESGO = {
    "horas_sueno": "bajo",
    "calidad_sueno": "bajo",
    "estado_basal": "bajo",
    "nivel_apoyo": "neutro",
    "salud_gi": "alto",
    "cambio_rutina": "alto",
    "desregulaciones_previas": "alto",
}

EXPLICACIONES = {
    "horas_sueno": {
        "riesgo": "Durmió menos horas de lo habitual la noche anterior.",
        "protector": "Durmió una cantidad de horas adecuada anoche.",
    },
    "calidad_sueno": {
        "riesgo": "La calidad del sueño de anoche fue mala o muy interrumpida.",
        "protector": "El sueño de anoche fue de buena calidad.",
    },
    "estado_basal": {
        "riesgo": "El estado de ánimo de hoy se muestra más irritable de lo esperado.",
        "protector": "El estado de ánimo de hoy se muestra tranquilo.",
    },
    "salud_gi": {
        "riesgo": "Hay malestar gastrointestinal relevante hoy.",
        "protector": "No hay malestar gastrointestinal relevante hoy.",
    },
    "cambio_rutina": {
        "riesgo": "Hubo un cambio de rutina drástico o inesperado.",
        "protector": "No hubo cambios de rutina relevantes hoy.",
    },
    "desregulaciones_previas": {
        "riesgo": "Se registran varias desregulaciones en los últimos días.",
        "protector": "No se registran desregulaciones recientes.",
    },
    "nivel_apoyo": {
        "riesgo": "El nivel de apoyo disponible hoy es más bajo de lo habitual.",
        "protector": "Hay un buen nivel de apoyo disponible hoy.",
    },
}

ACCIONES = {
    "horas_sueno": "Prioriza una siesta corta o un descanso temprano esta noche.",
    "calidad_sueno": "Refuerza la rutina de sueño: luces bajas, mismo horario y baja estimulación antes de dormir.",
    "estado_basal": "Anticipa transiciones con aviso previo y ten disponible un espacio de calma.",
    "salud_gi": "Registra la alimentación de hoy y coméntalo con el equipo terapéutico si el malestar persiste.",
    "cambio_rutina": "Reintroduce anclas conocidas (objeto, música, horario) para compensar el cambio.",
    "desregulaciones_previas": "Reduce estímulos sensoriales en las próximas horas y prioriza pausas de descanso.",
    "nivel_apoyo": "Coordina con la red de apoyo (familia, escuela, terapeuta) para reforzar la contención hoy.",
}


def cargar_datos(ruta_csv: str) -> pd.DataFrame:
    return pd.read_csv(ruta_csv)


def entrenar_modelo(df_historico: pd.DataFrame):
    """
    Entrena el imputador MICE y el Random Forest sobre los registros
    históricos que ya tienen una etiqueta crisis_24h conocida
    (misma lógica que PASO 3 y PASO 4 de 1.py).
    """
    df_etiquetado = df_historico.dropna(subset=[LABEL])
    df_etiquetado = df_etiquetado[df_etiquetado[LABEL] != ""]

    X = df_etiquetado[FEATURES].apply(pd.to_numeric, errors="coerce")
    y = df_etiquetado[LABEL].astype(int)

    imputador = IterativeImputer(max_iter=10, random_state=42, sample_posterior=False)
    X_imputado = imputador.fit_transform(X)
    X_imputado = pd.DataFrame(X_imputado, columns=FEATURES)
    for col in COLS_ORDINALES:
        X_imputado[col] = X_imputado[col].round()

    modelo_rf = RandomForestClassifier(n_estimators=200, random_state=42)
    modelo_rf.fit(X_imputado, y)

    return modelo_rf, imputador


def _completitud(registro: dict) -> float:
    provistos = sum(1 for f in FEATURES if registro.get(f) is not None)
    return provistos / len(FEATURES)


def predecir(registro: dict, modelo_rf, imputador, n_historico: int):
    """
    registro: dict con las mismas llaves que FEATURES.
    Los campos no informados por la familia deben venir como None
    (se completan mediante imputación MICE, igual que en 1.py).
    """
    fila = pd.DataFrame([{f: registro.get(f, np.nan) for f in FEATURES}])
    fila = fila.apply(pd.to_numeric, errors="coerce")
    fila_imputada = pd.DataFrame(imputador.transform(fila), columns=FEATURES)
    for col in COLS_ORDINALES:
        fila_imputada[col] = fila_imputada[col].round()

    probabilidad = float(modelo_rf.predict_proba(fila_imputada)[0][1]) * 100

    if probabilidad < 33:
        nivel = "bajo"
    elif probabilidad < 66:
        nivel = "medio"
    else:
        nivel = "alto"

    completitud = _completitud(registro)
    # La confianza combina cuántos campos informó la familia hoy y cuántos
    # registros históricos respaldan al modelo entrenado.
    confianza = 100 * (0.6 * completitud + 0.4 * min(n_historico / 500, 1.0))
    confianza = max(20.0, min(99.0, confianza))

    importancias = modelo_rf.feature_importances_
    contribuciones = []
    for i, feature in enumerate(FEATURES):
        valor = fila_imputada.iloc[0][feature]
        direccion = DIRECCION_RIESGO[feature]
        if direccion == "bajo":
            hacia_riesgo = -valor
        elif direccion == "alto":
            hacia_riesgo = valor
        else:
            hacia_riesgo = 0
        contribuciones.append((feature, importancias[i] * hacia_riesgo))

    contribuciones.sort(key=lambda x: x[1], reverse=True)

    factores, acciones = [], []
    for feature, score in contribuciones:
        if len(factores) >= 3:
            break
        if score <= 0:
            continue
        factores.append(EXPLICACIONES[feature]["riesgo"])
        acciones.append(ACCIONES[feature])

    if not factores:
        for feature, _ in contribuciones[:2]:
            factores.append(EXPLICACIONES[feature]["protector"])
        acciones.append("Mantén la rutina actual: hoy no hay señales que sugieran ajustes.")

    completeness_note = ""
    if completitud < 1.0:
        faltantes = [f for f in FEATURES if registro.get(f) is None]
        completeness_note = (
            f"Se imputaron {len(faltantes)} de {len(FEATURES)} variables por falta de registro; "
            "la confianza de esta predicción es menor."
        )

    return {
        "risk_level": nivel,
        "probability": round(probabilidad, 1),
        "confidence": round(confianza, 1),
        "factors": factores[:3],
        "actions": acciones[:3],
        "completeness_note": completeness_note,
    }
