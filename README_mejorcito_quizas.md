# Propuesta Bluba — Anticipación de crisis conductual con ML

Datatón FICA UFRO × Bluba SpA. Este documento explica **cada archivo
presente en este repositorio** y cómo encaja en el esquema general del
proyecto. Todo lo descrito aquí fue verificado corriendo el backend contra
este mismo zip antes de escribirlo.

## 1. La idea en una imagen

```
                              ┌─────────────────────────────┐
                              │   propuesta-bluba-ml.html    │
                              │        (front-end)           │
                              └───────────┬──────────┬───────┘
                                          │          │
                          fetch HTTP      │          │  Web Serial API
                       (sección "Demo")   │          │  (sección "Juguete en vivo")
                                          ▼          ▼
                        ┌──────────────────────┐   Arduino (USB o Bluetooth
                        │  backend/app.py       │   pareado como puerto COM),
                        │  (Flask, puerto 5000) │   firmware sketch_bluba_original.ino
                        └──────────┬───────────┘   — lectura DIRECTA desde el
                                   │                navegador, sin pasar por Flask
        ┌──────────────────────────┼──────────────────────────┬───────────────┐
        ▼                          ▼                          ▼               ▼
 backend/modelo.py      backend/personalizacion.py   backend/detonantes.py  backend/sensores.py
 (MICE + Random Forest)  (baseline + shrinkage,        (detonantes/estrategias (umbrales del
        │                 compartido)                  reales, CSV del concurso) juguete —
        ▼                                                       │               ver §4.6)
 backend/base_bluba.csv                              backend/data/*.csv
 (la "base de datos", CSV)                           (datos reales anonimizados)
        ▲
        │ generado una vez por
 backend/seed_dataset.py
```

Hay **dos caminos independientes** desde el HTML hacia el juguete:
1. La sección **"Demo"** habla con el backend Flask (predicción de crisis).
2. La sección **"Juguete en vivo"** lee el Arduino **directo desde el
   navegador** (Web Serial), sin pasar por Flask — por eso el diagrama la
   dibuja aparte. Más detalle en §3 y §4.6.

## 2. Archivos en la raíz

| Archivo | Qué es |
|---|---|
| `README.md` | El README anterior de este repo (instrucciones rápidas). Este documento que estás leyendo lo reemplaza/complementa con el detalle completo de cada archivo. |
| `LICENSE` | Licencia MIT del repositorio. |
| `propuesta-bluba-ml.html` | El front-end completo: la propuesta navegable (contexto, pipeline, requisitos) más dos piezas interactivas — la demo de predicción y las alertas en vivo del juguete. Se abre directo en el navegador, sin build. Detalle de sus secciones en §3. |

## 3. `propuesta-bluba-ml.html` — secciones

Página de una sola vista, en este orden: **Hero** (pregunta activadora),
**Organizadores**, **`#desafio`** (contexto del reto), **`#demo`**
(formulario + predicción), **`#juguete`** (alertas en vivo del dado),
**`#solucion`** (pipeline de 5 etapas), **`#requisitos`** (respuesta a cada
requisito de Bluba), **`#datos`** (señales que observa el modelo), **metas
de diseño**, **`#etica`**, y el **footer**.

### 3.1 Sección `#demo` — habla con el backend Flask

- **Formulario** (`<form id="crisis-form">`): selector de `usuario_id` con
  tres familias sintéticas (`familia_demo_01/02/03`) **y los 4 casos reales
  del concurso** (`PAC-001`...`PAC-004`), más los campos del micro-registro
  diario (horas de sueño, calidad del sueño, ánimo, nivel de apoyo,
  malestar GI, cambio de rutina, desregulaciones **en los últimos 3 días**
  —número explícito, no ambiguo—, alimentación e interacción social —estas
  dos se guardan pero el modelo aún no las usa—, y notas libres). Cada
  select tiene "Sin datos" → se envía como `null`.
- **JS**: hace `fetch` a `${API_BASE_URL}/api/prediccion`
  (`API_BASE_URL = 'http://localhost:5000'`, constante al inicio del
  `<script>` — cámbiala si despliegas el backend en otra URL) y renderiza
  nivel de riesgo, probabilidad a 24h, confianza, factores y acciones.
- **Si eliges un `PAC-00x`**, además aparece el bloque **"Lo que ya sabemos
  de este niño/a"**: diagnóstico, perfil sensorial, eventos de crisis
  documentados y qué estrategias le han funcionado antes — viene del campo
  `known_profile` de la respuesta, que solo se llena para esos 4 casos
  reales (ver `detonantes.py` en §4.2).

### 3.2 Sección `#juguete` — Web Serial, **no** usa el backend

Botón "Conectar juguete" que llama a `navigator.serial.requestPort()` del
propio navegador: abre el puerto (USB o el COM virtual que crea Windows al
emparejar el HC-06 por Bluetooth), lee línea por línea lo que transmite
`sketch_bluba_original.ino`, y muestra un banner cuando detecta
`"¡ALERTA! ..."`. **No llama a ningún endpoint de Flask** — es intencional:
el firmware sigue siendo el original, sin calibración por niño/a (ver
§4.6). Solo funciona en Chrome/Edge de escritorio.

## 4. Carpeta `backend/`

### 4.1 Cómo correrlo

```bash
cd backend
pip install -r requirements.txt
python seed_dataset.py     # ya viene un CSV de ejemplo, pero puedes regenerarlo
python app.py              # API en http://localhost:5000
```

Verificado: con esto corriendo, `POST /api/prediccion` responde 200 y guarda
la fila en `base_bluba.csv`; para un `usuario_id` real (`PAC-001`...`004`)
la respuesta incluye `known_profile` con datos reales.

### 4.2 Archivo por archivo

| Archivo | Rol en el esquema general |
|---|---|
| `requirements.txt` | Dependencias del servidor: `flask`, `flask-cors`, `pandas`, `scikit-learn`, `numpy`. |
| `requirements-bridge.txt` | Dependencias (`pyserial`, `requests`) para un script puente Bluetooth que **ya no está en este repo** — ver la nota en §4.6. |
| `README.md` | README anterior de esta carpeta. **Parcialmente desactualizado**: describe `bridge_bluetooth.py` y `sketch_bluba_personalizado.ino` como si existieran; ninguno de los dos está en este zip (ver §4.6). |
| `seed_dataset.py` | Genera `base_bluba.csv` desde cero: 50 usuarios sintéticos × 30 días = 1.500 registros, con una fórmula de riesgo sintética que produce la etiqueta `crisis_24h`. Se corre una vez; después `app.py` va agregando filas reales de uso. |
| `base_bluba.csv` | La "base de datos": `usuario_id, fecha, horas_sueno, calidad_sueno, estado_basal, nivel_apoyo, salud_gi, cambio_rutina, desregulaciones_previas, alimentacion, interaccion_social, notas, crisis_24h`. 1.500 filas sintéticas de partida; cada predicción desde el HTML agrega una fila nueva (`crisis_24h` vacío, porque su desenlace real aún no se conoce). |
| `personalizacion.py` | Módulo **compartido** y genérico de personalización: dado un DataFrame, columnas e `id_col`, calcula media/std propia de cada id (`calcular_baselines`), la encoge (*shrinkage*, `K_SHRINKAGE_DEFECTO=10`) hacia el promedio poblacional según cuántas filas tiene ese id, y agrega columnas `{feature}_z` (`agregar_zscores`). No sabe nada de sueño ni de crisis a propósito — lo reutilizan `modelo.py` y `sensores.py` sin duplicar la lógica. |
| `modelo.py` | El corazón predictivo. 7 variables (`FEATURES`), imputación con `IterativeImputer` (MICE, como en el script original `1.py` del equipo), baselines personales vía `personalizacion.py`, un único `RandomForestClassifier` entrenado sobre valores crudos + z-scores (`entrenar_modelo`), y la predicción final con nivel de riesgo, probabilidad, confianza, factores explicativos y acciones (`predecir`). `VENTANA_DESREGULACIONES_DIAS = 3` deja explícito que `desregulaciones_previas` es un conteo de 3 días, no un período ambiguo — se refleja tanto en el texto que genera esta función como en la etiqueta del HTML. |
| `detonantes.py` | Detonantes y estrategias **reales** (no sintéticas) por niño/a, a partir de `backend/data/1_casos_anonimizados.csv` y `backend/data/5_eventos_desregulacion_tutor.csv` (los datos anonimizados entregados para el concurso). `perfil_conocido(usuario_id)` devuelve diagnóstico, perfil sensorial, eventos documentados (detonante + estrategia + si funcionó) y las estrategias que sí lograron "Regulación Exitosa" — o `None` si el id no es uno de los 4 casos reales. Es una capa **independiente** del modelo: no cambia el Random Forest ni sus variables. |
| `sensores.py` | Procesamiento de las señales del juguete sensorial. Aplica el mismo principio de `personalizacion.py` a los eventos del dado: los agrega en un CSV propio (`sensores_bluba.csv`, no incluido — se crea al recibir el primer evento), los resume por día/niño y calcula un umbral de "movimiento brusco"/"clic rápido" propio de cada uno (`calcular_umbrales_personalizados`), con 0.6/300ms por defecto si no hay historial. Ver estado real de uso en §4.6. |
| `app.py` | La API Flask. `GET /api/salud`; `POST /api/prediccion` (guarda el registro y devuelve la predicción, con `known_profile` embebido); `GET /api/historial/<usuario_id>`; `GET /api/detonantes/<usuario_id>` (expone `detonantes.py` directo); y tres endpoints del juguete —`POST /api/sensor/evento`, `GET /api/sensor/umbral/<usuario_id>`, `GET /api/sensor/resumen/<usuario_id>`— que delegan en `sensores.py` (ver §4.6 sobre su estado actual). CORS abierto para la demo local. |
| `arduino/sketch_bluba_original.ino` | Firmware del dado (joystick + botón + HC-06), **sin modificar**: umbrales fijos (`thresholdMovimiento=0.6`, `thresholdDobleClic=300`), igual para todos los niños. Es el que lee la sección `#juguete` del HTML por Web Serial. |
| `backend/data/1_casos_anonimizados.csv` | Dato real del concurso: ficha de los 4 casos (edad, diagnóstico, perfil sensorial predominante). Insumo de `detonantes.py`. |
| `backend/data/5_eventos_desregulacion_tutor.csv` | Dato real del concurso: 7 eventos de crisis documentados (detonante exacto, estrategia usada, si funcionó). Insumo de `detonantes.py`. |

### 4.3 Endpoints de la API — resumen

| Endpoint | Usa | Llamado por |
|---|---|---|
| `GET /api/salud` | — | chequeo manual |
| `POST /api/prediccion` | `modelo.py`, `detonantes.py` | sección `#demo` del HTML |
| `GET /api/historial/<usuario_id>` | `base_bluba.csv` | nadie en este repo (disponible para usar) |
| `GET /api/detonantes/<usuario_id>` | `detonantes.py` | nadie en este repo directamente (la misma info ya viaja embebida en `/api/prediccion`) |
| `POST /api/sensor/evento` | `sensores.py` | nadie en este repo (ver §4.6) |
| `GET /api/sensor/umbral/<usuario_id>` | `sensores.py` | nadie en este repo (ver §4.6) |
| `GET /api/sensor/resumen/<usuario_id>` | `sensores.py` | nadie en este repo (ver §4.6) |

### 4.4 Personalización por niño/a — la idea que atraviesa el proyecto

En vez de un modelo (o firmware) distinto por niño/a, se personaliza el
**input**: cada valor se compara contra el propio historial del niño/a
(z-score), con *shrinkage* hacia la población cuando el historial es corto.
Esta misma idea se aplica dos veces: en `modelo.py` (sueño, ánimo, etc.,
vía `personalizacion.py`) y en `sensores.py` (intensidad del juguete),
reutilizando el mismo módulo compartido.

### 4.5 Datos reales del concurso — qué se integró y por qué

De los 5 CSV entregados para el concurso, solo dos tenían cadencia
diaria/de eventos útil para un predictor: `4_seguimiento_diario_tutor`
(inspiró las variables de `modelo.py`) y `5_eventos_desregulacion_tutor`
(las crisis reales, con detonante y estrategia). Se decidió **no** tocar el
modelo entrenado (sigue siendo sintético, por lo escaso del dataset real:
solo 7 eventos en 4 niños) y en su lugar agregar `detonantes.py` como capa
separada y opcional, que solo aporta información cuando el `usuario_id` es
uno de los 4 casos reales.

### 4.6 Lo que quedó pendiente / inconsistente

- **El juguete sensorial personalizado no está conectado de punta a punta.**
  `sensores.py` y los 3 endpoints `/api/sensor/*` siguen en el código y
  funcionan si los llamas directo (`curl`, Postman), pero el script que los
  alimentaría automáticamente (un puente que lea el Arduino por serial y
  reenvíe cada evento a `POST /api/sensor/evento`) no está en este repo, y
  el firmware presente (`sketch_bluba_original.ino`) tiene umbral fijo, no
  el que recibe calibración por Bluetooth. En la práctica, hoy el juguete
  solo se usa de la forma simple: alertas en vivo leídas directo por Web
  Serial (sección `#juguete` del HTML), sin ninguna personalización.
- **Dos READMEs desactualizados** (`README.md` de la raíz y
  `backend/README.md`) siguen mencionando `bridge_bluetooth.py` y
  `sketch_bluba_personalizado.ino` como si existieran. Este documento los
  reemplaza en cuanto a exactitud; vale la pena borrar o reescribir esos
  dos para no dejar información contradictoria en el repo.
- **`requirements-bridge.txt`** no tiene ningún script que lo use todavía.

### 4.7 Limitaciones conocidas (para defender ante el jurado)

- El baseline de personalización usa **todo** el historial disponible de
  un usuario, no solo los días anteriores al registro evaluado — hay una
  leve fuga de información en el entrenamiento. Para producción conviene
  una versión expansiva/rolling.
- El modelo se reentrena completo cada vez que cambia el número de filas
  del CSV; con un dataset más grande convendría cachear y reentrenar bajo
  demanda.
- `crisis_24h` en los registros nuevos queda vacío porque su desenlace real
  aún no se conoce al momento de guardar el registro.
- Los detonantes/estrategias reales (`detonantes.py`) solo cubren 4 niños
  con 7 eventos — es un complemento puntual, no cobertura general.
