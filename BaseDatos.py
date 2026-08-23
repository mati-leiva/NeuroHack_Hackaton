import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 1. Configuración de la simulación
n_usuarios = 50  # Cantidad de usuarios distintos
dias_por_usuario = 30  # Cuántos días de seguimiento por usuario
n_registros = n_usuarios * dias_por_usuario

print(f"Generando {n_registros} registros en total...")

# 2. Generar IDs de usuarios y secuencia de fechas
# Repetimos cada ID de usuario la cantidad de días
usuarios = np.repeat(np.arange(1, n_usuarios + 1), dias_por_usuario)

# Generamos un rango de fechas y lo multiplicamos por la cantidad de usuarios
fecha_inicio = pd.to_datetime("2026-08-01")
fechas = (
    pd.date_range(start=fecha_inicio, periods=dias_por_usuario).tolist() * n_usuarios
)

# 3. Generar las variables (con las probabilidades definidas)
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

# NUEVA VARIABLE: Desregulaciones previas usando distribución de Poisson
desregulaciones_previas = np.random.poisson(lam=0.8, size=n_registros).clip(0, 5)

# 4. Construir el DataFrame
df = pd.DataFrame(
    {
        "usuario_id": usuarios,
        "fecha": fechas,
        "calidad_sueno": calidad_sueno,
        "estado_basal": estado_basal,
        "nivel_apoyo": nivel_apoyo,
        "salud_gi": salud_gi,
        "cambio_rutina": cambio_rutina,
        "desregulaciones_previas": desregulaciones_previas,  # Columna agregada
    }
)

# 5. Exportar a CSV
nombre_archivo = "base_de_datos_con_desregulaciones.csv"
df.to_csv(nombre_archivo, index=False)

print(f"¡Listo! Base de datos guardada como '{nombre_archivo}'")
print("\nPrimeras 5 filas generadas:")
print(df.head())
