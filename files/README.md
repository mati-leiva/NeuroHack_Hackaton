# Backend Bluba — API + base de datos CSV

Este backend recibe el micro-registro diario desde el HTML, lo guarda como
fila nueva en `base_bluba.csv` y devuelve la predicción del modelo (MICE +
Random Forest, adaptado de tu `1.py`).

## 1. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

## 2. Crear la base de datos (una sola vez)

```bash
python seed_dataset.py
```

Esto genera `base_bluba.csv` con 1.500 registros históricos sintéticos
(50 usuarios x 30 días), combinando la estructura de tu `BaseDatos.py`
con la fórmula de riesgo de tu `1.py`. Ya viene incluido un CSV de ejemplo
en esta carpeta, pero puedes regenerarlo cuando quieras.

## 3. Levantar la API

```bash
python app.py
```

Queda escuchando en `http://localhost:5000`.

## 4. Abrir el HTML

Abre `propuesta-bluba-ml.html` normalmente en el navegador (doble clic o
`Live Server`). El formulario de la sección "Demo" llama a
`http://localhost:5000/api/prediccion`. Si despliegas la API en otra URL,
cambia la constante `API_BASE_URL` al inicio del `<script>` del HTML.

## Endpoints

- `GET /api/salud` → chequeo simple, responde `{"status": "ok"}`.
- `POST /api/prediccion` → guarda el registro del día en el CSV y devuelve
  la predicción (`risk_level`, `probability`, `confidence`, `factors`,
  `actions`, `completeness_note`).
- `GET /api/historial/<usuario_id>` → últimos 10 registros de un usuario.

## Notas sobre el modelo

- Variables que sí usa el modelo (igual que en `1.py`): `horas_sueno`,
  `calidad_sueno`, `estado_basal`, `nivel_apoyo`, `salud_gi`,
  `cambio_rutina`, `desregulaciones_previas`.
- Variables que el CSV guarda pero el modelo aún no usa como predictoras:
  `alimentacion`, `interaccion_social`, `notas` (quedan disponibles para
  cuando quieran ampliar el modelo).
- Cada campo puede llegar como `null` ("sin datos" en el HTML); el backend
  los imputa con `IterativeImputer` (MICE) antes de predecir, igual que en
  el PASO 3 de tu `1.py`.
- El modelo se reentrena automáticamente cada vez que cambia el número de
  filas del CSV (es decir, cada vez que se guarda un registro nuevo). Para
  un dataset más grande convendría cachear el entrenamiento y
  reentrenar solo cada cierto tiempo o bajo demanda.
- La columna `crisis_24h` de los registros nuevos queda vacía porque su
  desenlace real (si hubo o no crisis) aún no se conoce en el momento del
  registro; solo se usa como etiqueta de entrenamiento en el histórico
  sintético inicial.
