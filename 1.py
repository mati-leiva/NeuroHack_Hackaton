import numpy as np
import pandas as pd

# En scikit-learn, IterativeImputer es experimental y debe habilitarse explícitamente
from sklearn.experimental import enable_iterative_imputer  # noqa
from sklearn.impute import IterativeImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

# -------------------------------------------------------------------------
# PASO 1: Generación del Dataset Sintético (Bitácora Bluba)
# -------------------------------------------------------------------------
np.random.seed(42)
n_registros = 1000

# Creación de variables basadas en la bitácora Bluba, utilizaremos variables ordinales
# Ya que es complicado asignar un numero a cada sentimiento o medicion.
horas_sueno = np.random.normal(loc=7.0, scale=1.5, size=n_registros).clip(3, 10)
calidad_sueno = np.random.choice(
    [1, 2, 3], size=n_registros, p=[0.3, 0.4, 0.3]
)  # 1:Mala, 2:Regular, 3:Buena
estado_basal = np.random.choice(
    [1, 2, 3], size=n_registros, p=[0.3, 0.5, 0.2]
)  # 1:Irritable, 2:Neutro, 3:Tranquilo
nivel_apoyo = np.random.choice(
    [1, 2, 3], size=n_registros, p=[0.4, 0.4, 0.2]
)  # 1:Alto, 2:Medio, 3:Bajo
salud_gi = np.random.choice(
    [1, 2, 3], size=n_registros, p=[0.7, 0.2, 0.1]
)  # 1:Normal, 2:Molestia Leve, 3:Severo
cambio_rutina = np.random.choice(
    [0, 1, 2], size=n_registros, p=[0.6, 0.3, 0.1]
)  # 0:Ninguno, 1:Leve, 2:Drástico
desregulaciones_previas = np.random.poisson(lam=0.8, size=n_registros).clip(0, 5)

df_real = pd.DataFrame(
    {
        "horas_sueno": horas_sueno,
        "calidad_sueno": calidad_sueno,
        "estado_basal": estado_basal,
        "nivel_apoyo": nivel_apoyo,
        "salud_gi": salud_gi,
        "cambio_rutina": cambio_rutina,
        "desregulaciones_previas": desregulaciones_previas,
    }
)

# Calculamos un riesgo segun factores claves, porcentajes al ojimetro

score_riesgo = (
    (10 - df_real["horas_sueno"]) * 0.35
    + (4 - df_real["calidad_sueno"]) * 0.40
    + (4 - df_real["estado_basal"]) * 0.50
    + df_real["salud_gi"] * 0.60
    + df_real["cambio_rutina"] * 0.75
    + df_real["desregulaciones_previas"] * 0.50
)

# Funcion de activacion, lo convertimos en un 0 o 1, habria que hacer alguna inferencia aqui o algo

prob_crisis = 1 / (1 + np.exp(-(score_riesgo - 6.0)))
df_real["crisis_24h"] = (np.random.binomial(1, prob_crisis)).astype(int)


# -------------------------------------------------------------------------
# PASO 2: Simulación de Datos Faltantes (20% de vacíos)
# -------------------------------------------------------------------------

df_incompleto = df_real.copy()
variables_features = [col for col in df_real.columns if col != "crisis_24h"]

# Se introducen NaNs de forma aleatoria en la bitácora
for col in variables_features:
    mask = np.random.rand(n_registros) < 0.20  # 20% faltante
    df_incompleto.loc[mask, col] = np.nan

print("--- REPORTE DE DATOS FALTANTES (SIMULADO) ---")
print(df_incompleto[variables_features].isnull().sum())
print("\n")


################# AI SLOP!! -> ver como se hace bien!!


# -------------------------------------------------------------------------
# PASO 3: Imputación Multivariada MICE con Scikit-Learn
# -------------------------------------------------------------------------
# IterativeImputer utiliza regresión en cadena para estimar cada variable faltante
imputador_mice = IterativeImputer(max_iter=10, random_state=42, sample_posterior=False)

# Ajuste e imputación
matriz_imputada = imputador_mice.fit_transform(df_incompleto[variables_features])
df_imputado = pd.DataFrame(matriz_imputada, columns=variables_features)

# Ajuste de redondeo para variables categóricas u ordinales
cols_ordinales = [
    "calidad_sueno",
    "estado_basal",
    "nivel_apoyo",
    "salud_gi",
    "cambio_rutina",
    "desregulaciones_previas",
]
for col in cols_ordinales:
    df_imputado[col] = df_imputado[col].round().astype(int)

print("--- DATO COMPROBATORIO: VALORES NULOS TRAS IMPUTACIÓN MICE ---")
print(df_imputado.isnull().sum().sum(), "valores nulos restantes.")
print("\n")

# -------------------------------------------------------------------------
# PASO 4: Entrenamiento del Modelo de Predicción de Crisis
# -------------------------------------------------------------------------
X = df_imputado
y = df_real["crisis_24h"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Modelo Random Forest sobre los datos reconstruidos con MICE
modelo_bluba = RandomForestClassifier(n_estimators=100, random_state=42)
modelo_bluba.fit(X_train, y_train)

# Predicción de probabilidades para las próximas 24 horas
probabilidades_test = modelo_bluba.predict_proba(X_test)[:, 1]
predicciones_binarias = (probabilidades_test >= 0.5).astype(int)

# -------------------------------------------------------------------------
# PASO 5: Resultados del Prototipo Analítico
# -------------------------------------------------------------------------
print("--- EVALUACIÓN DEL MODELO PREDICTIVO ---")
print("ROC-AUC Score:", round(roc_auc_score(y_test, probabilidades_test), 3))
print("\nReporte de Clasificación:")
print(classification_report(y_test, predicciones_binarias))

# Ejemplo de predicción para un caso individual
nuevo_registro = pd.DataFrame(
    [
        {
            "horas_sueno": 4.5,
            "calidad_sueno": 1,  # Mala
            "estado_basal": 1,  # Irritable
            "nivel_apoyo": 1,  # Alto apoyo
            "salud_gi": 2,  # Molestia leve
            "cambio_rutina": 2,  # Cambio drástico
            "desregulaciones_previas": 2,
        }
    ]
)

prob_caso = modelo_bluba.predict_proba(nuevo_registro)[0][1]
print(f"--- EJEMPLO EN VIVO PARA PITCH ---")
print(
    f"Probabilidad de crisis calculada para el caso de prueba: {prob_caso * 100:.1f}%"
)
