"""
Lógica de imputación (MICE), personalización por niño/a mediante baselines
individuales, y modelo predictivo (Random Forest) — adaptada de 1.py — para
trabajar sobre la base de datos acumulada en base_bluba.csv.

Idea de personalización (sin entrenar un modelo por niño):
en vez de que el modelo vea solo el valor crudo de hoy (p.ej. "durmió 6h"),
también ve cuánto se aleja ese valor del propio promedio histórico del niño
o niña, en desviaciones estándar (z-score). Un mismo Random Forest global
aprende sobre esa señal relativa, que ya es personal por construcción.

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
FEATURES_Z = [f + "_z" for f in FEATURES]
COLUMNAS_MODELO = FEATURES + FEATURES_Z  # el RF ve el valor crudo Y el relativo
LABEL = "crisis_24h"

COLS_ORDINALES = [
    "calidad_sueno",
    "estado_basal",
    "nivel_apoyo",
    "salud_gi",
    "cambio_rutina",
    "desregulaciones_previas",
]

# Cuántos "días equivalentes" de peso le damos a la media poblacional en el
# encogimiento (shrinkage). Con k_shrinkage=10: un niño con 10 días propios
# de historial pesa 50/50 entre su propio promedio y el de la población;
# con 30+ días, su propio patrón domina casi por completo.
K_SHRINKAGE = 10
STD_MINIMO = 0.25  # evita dividir por std≈0 cuando un niño es muy estable

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

# Plantillas de explicación PERSONALIZADA: comparan contra el propio
# historial del niño/a en vez de dar un juicio absoluto.
PLANTILLAS_RIESGO = {
    "horas_sueno": "Durmió {intensidad} menos horas que su propio promedio habitual.",
    "calidad_sueno": "La calidad del sueño de anoche fue {intensidad} peor que lo habitual para él o ella.",
    "estado_basal": "Su ánimo hoy está {intensidad} más irritable que su estado basal habitual.",
    "salud_gi": "El malestar gastrointestinal de hoy es {intensidad} mayor que lo habitual para él o ella.",
    "cambio_rutina": "El cambio de rutina de hoy es {intensidad} mayor de lo que suele manejar sin dificultad.",
    "desregulaciones_previas": "Las desregulaciones de los últimos días son {intensidad} más frecuentes que su patrón habitual.",
    "nivel_apoyo": "El apoyo disponible hoy es {intensidad} menor que lo habitual para él o ella.",
}
PLANTILLAS_PROTECTOR = {
    "horas_sueno": "Durmió una cantidad de horas similar o mejor que su propio promedio.",
    "calidad_sueno": "La calidad del sueño de hoy está en línea con lo habitual para él o ella.",
    "estado_basal": "Su ánimo hoy está dentro de su rango habitual de tranquilidad.",
    "salud_gi": "No hay malestar gastrointestinal por sobre lo habitual para él o ella.",
    "cambio_rutina": "No hay cambios de rutina por sobre lo que suele manejar bien.",
    "desregulaciones_previas": "Las desregulaciones están dentro de su patrón habitual.",
    "nivel_apoyo": "El apoyo disponible hoy está en línea con lo habitual.",
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


# ---------------------------------------------------------------------------
# Personalización: baseline (media, std) por niño/a, con shrinkage hacia la
# población para que un niño nuevo (poco historial) no dependa de un
# promedio propio poco confiable.
# ---------------------------------------------------------------------------
def calcular_baselines(df_historico: pd.DataFrame, k_shrinkage: int = K_SHRINKAGE):
    """
    Devuelve:
      - baseline_df: DataFrame indexado por usuario_id con {feature}_media y
        {feature}_std ya encogidos hacia la población.
      - baseline_poblacion: dict {feature: {"media":.., "std":..}} usado como
        respaldo para usuarios sin ningún historial todavía.

    NOTA (simplificación de prototipo): el baseline de un usuario se calcula
    con TODO su historial disponible, sin excluir el propio día evaluado
    (hay una leve fuga de información al entrenar). Para producción conviene
    un baseline expansivo que solo mire días anteriores a cada registro.
    """
    baseline_poblacion = {}
    for f in FEATURES:
        serie = pd.to_numeric(df_historico[f], errors="coerce")
        media = serie.mean()
        std = serie.std()
        baseline_poblacion[f] = {
            "media": 0.0 if pd.isna(media) else media,
            "std": std if (std and not pd.isna(std) and std > 0) else 1.0,
        }

    filas = []
    for usuario_id, grupo in df_historico.groupby(df_historico["usuario_id"].astype(str)):
        n = len(grupo)
        peso = n / (n + k_shrinkage)
        fila = {"usuario_id": usuario_id, "n_dias": n}
        for f in FEATURES:
            serie = pd.to_numeric(grupo[f], errors="coerce")
            media_usr, std_usr = serie.mean(), serie.std()
            media_pob, std_pob = baseline_poblacion[f]["media"], baseline_poblacion[f]["std"]
            if pd.isna(media_usr):
                media_usr = media_pob
            if pd.isna(std_usr) or std_usr == 0:
                std_usr = std_pob
            fila[f + "_media"] = peso * media_usr + (1 - peso) * media_pob
            fila[f + "_std"] = max(peso * std_usr + (1 - peso) * std_pob, STD_MINIMO)
        filas.append(fila)

    baseline_df = pd.DataFrame(filas).set_index("usuario_id") if filas else pd.DataFrame()
    return baseline_df, baseline_poblacion


def _agregar_zscores(df: pd.DataFrame, baseline_df: pd.DataFrame, baseline_poblacion: dict) -> pd.DataFrame:
    """Agrega columnas {feature}_z usando el baseline personal de cada usuario_id."""
    df = df.copy()
    df["usuario_id"] = df["usuario_id"].astype(str)
    cols_baseline = [f + "_media" for f in FEATURES] + [f + "_std" for f in FEATURES]

    if not baseline_df.empty:
        df = df.merge(baseline_df[cols_baseline], how="left", left_on="usuario_id", right_index=True)
    else:
        for col in cols_baseline:
            df[col] = np.nan

    for f in FEATURES:
        media_col = df[f + "_media"].fillna(baseline_poblacion[f]["media"])
        std_col = df[f + "_std"].fillna(baseline_poblacion[f]["std"]).clip(lower=STD_MINIMO)
        valor = pd.to_numeric(df[f], errors="coerce")
        df[f + "_z"] = (valor - media_col) / std_col

    return df.drop(columns=cols_baseline)


def _dias_historial_usuario(baseline_df: pd.DataFrame, usuario_id) -> int:
    usuario_id = str(usuario_id)
    if baseline_df.empty or usuario_id not in baseline_df.index:
        return 0
    return int(baseline_df.loc[usuario_id, "n_dias"])


# ---------------------------------------------------------------------------
# Entrenamiento (mismo Random Forest para todos los niños y niñas)
# ---------------------------------------------------------------------------
def entrenar_modelo(df_historico: pd.DataFrame):
    """
    Entrena el imputador MICE, calcula los baselines personales y entrena
    UN solo Random Forest sobre valores crudos + z-scores personalizados
    (misma lógica de PASO 3/4 de 1.py, más la capa de personalización).
    """
    baseline_df, baseline_poblacion = calcular_baselines(df_historico)

    df_etiquetado = df_historico.dropna(subset=[LABEL])
    df_etiquetado = df_etiquetado[df_etiquetado[LABEL] != ""]

    X_raw = df_etiquetado[FEATURES].apply(pd.to_numeric, errors="coerce")
    imputador = IterativeImputer(max_iter=10, random_state=42, sample_posterior=False)
    X_imputado = pd.DataFrame(
        imputador.fit_transform(X_raw), columns=FEATURES, index=df_etiquetado.index
    )
    for col in COLS_ORDINALES:
        X_imputado[col] = X_imputado[col].round()
    X_imputado["usuario_id"] = df_etiquetado["usuario_id"].values

    X_con_z = _agregar_zscores(X_imputado, baseline_df, baseline_poblacion)
    X_final = X_con_z[COLUMNAS_MODELO]
    y = df_etiquetado[LABEL].astype(int)

    modelo_rf = RandomForestClassifier(n_estimators=200, random_state=42)
    modelo_rf.fit(X_final, y)

    return modelo_rf, imputador, baseline_df, baseline_poblacion


def _completitud(registro: dict) -> float:
    provistos = sum(1 for f in FEATURES if registro.get(f) is not None)
    return provistos / len(FEATURES)


def predecir(
    registro: dict,
    usuario_id,
    modelo_rf,
    imputador,
    baseline_df: pd.DataFrame,
    baseline_poblacion: dict,
    n_historico: int,
):
    """
    registro: dict con las mismas llaves que FEATURES (None = sin datos).
    usuario_id: identifica de quién es el registro, para aplicar SU baseline.
    """
    fila = pd.DataFrame([{f: registro.get(f, np.nan) for f in FEATURES}])
    fila = fila.apply(pd.to_numeric, errors="coerce")
    fila_imputada = pd.DataFrame(imputador.transform(fila), columns=FEATURES)
    for col in COLS_ORDINALES:
        fila_imputada[col] = fila_imputada[col].round()
    fila_imputada["usuario_id"] = usuario_id

    fila_con_z = _agregar_zscores(fila_imputada, baseline_df, baseline_poblacion)
    X_pred = fila_con_z[COLUMNAS_MODELO]

    probabilidad = float(modelo_rf.predict_proba(X_pred)[0][1]) * 100

    if probabilidad < 33:
        nivel = "bajo"
    elif probabilidad < 66:
        nivel = "medio"
    else:
        nivel = "alto"

    dias_historial = _dias_historial_usuario(baseline_df, usuario_id)
    completitud = _completitud(registro)
    # La confianza combina: cuántos campos informó la familia hoy, cuántos
    # registros históricos respaldan al modelo en general, y cuánto
    # historial propio tiene ESTE niño/a para que su baseline sea confiable.
    confianza = 100 * (
        0.45 * completitud
        + 0.30 * min(n_historico / 500, 1.0)
        + 0.25 * min(dias_historial / 20, 1.0)
    )
    confianza = max(20.0, min(99.0, confianza))

    importancias = dict(zip(COLUMNAS_MODELO, modelo_rf.feature_importances_))
    contribuciones = []
    for f in FEATURES:
        z = float(fila_con_z.iloc[0][f + "_z"])
        direccion = DIRECCION_RIESGO[f]
        if direccion == "bajo":
            hacia_riesgo = -z
        elif direccion == "alto":
            hacia_riesgo = z
        else:
            hacia_riesgo = 0
        contribuciones.append((f, z, importancias[f + "_z"] * hacia_riesgo))

    contribuciones.sort(key=lambda x: x[2], reverse=True)

    factores, acciones = [], []
    for f, z, score in contribuciones:
        if len(factores) >= 3:
            break
        if score <= 0:
            continue
        intensidad = "considerablemente" if abs(z) >= 1.5 else "levemente"
        factores.append(PLANTILLAS_RIESGO[f].format(intensidad=intensidad))
        acciones.append(ACCIONES[f])

    if not factores:
        for f, _, _ in contribuciones[:2]:
            factores.append(PLANTILLAS_PROTECTOR[f])
        acciones.append("Mantén la rutina actual: hoy no hay señales que sugieran ajustes.")

    notas = []
    if completitud < 1.0:
        faltantes = [f for f in FEATURES if registro.get(f) is None]
        notas.append(
            f"Se imputaron {len(faltantes)} de {len(FEATURES)} variables por falta de registro."
        )
    if dias_historial < 5:
        notas.append(
            f"Este niño/a aún tiene poco historial propio ({dias_historial} días); "
            "la predicción se apoya principalmente en el patrón poblacional."
        )

    return {
        "risk_level": nivel,
        "probability": round(probabilidad, 1),
        "confidence": round(confianza, 1),
        "factors": factores[:3],
        "actions": acciones[:3],
        "completeness_note": " ".join(notas),
    }
