# Propuesta Bluba — ML de anticipación de crisis conductual

Datatón FICA UFRO × Bluba SpA. Contenido de esta carpeta:

```
propuesta-bluba/
├── propuesta-bluba-ml.html     ← front-end de la propuesta (ábrelo en el navegador)
└── backend/                    ← API + modelo + integración con el juguete
    ├── README.md                 instrucciones detalladas de instalación y uso
    ├── requirements.txt           dependencias del servidor (Flask, sklearn, pandas...)
    ├── requirements-bridge.txt    dependencias del script puente Bluetooth
    ├── seed_dataset.py            genera la base de datos inicial (CSV)
    ├── base_bluba.csv             base de datos de ejemplo ya generada
    ├── personalizacion.py         baseline + shrinkage por niño/a (compartido)
    ├── modelo.py                  imputación MICE + Random Forest
    ├── sensores.py                 procesamiento de señales del juguete (modo personalizado)
    ├── app.py                     API Flask (endpoints del registro y del sensor)
    ├── bridge_bluetooth.py        puente HC-06 (Arduino) -> API (modo personalizado)
    └── arduino/
        ├── sketch_bluba_original.ino        firmware ORIGINAL (umbral fijo) — en uso ahora
        └── sketch_bluba_personalizado.ino   firmware con umbral calibrable por Bluetooth
```

## Qué puedes hacer con esto, en tres niveles

### 1. Ver la propuesta (sin instalar nada)
Abre `propuesta-bluba-ml.html` en el navegador. Contexto, pipeline, requisitos
y una demo interactiva, todo navegable.

### 2. Probar la predicción de crisis con el modelo real
```bash
cd backend
pip install -r requirements.txt
python seed_dataset.py     # ya viene un CSV de ejemplo, pero puedes regenerarlo
python app.py              # API en http://localhost:5000
```
Con esto corriendo, la sección "Demo" del HTML guarda el micro-registro en
`base_bluba.csv` y devuelve una predicción real (riesgo, probabilidad,
confianza, factores y acciones) calculada por MICE + Random Forest.

### 3. Ver alertas en vivo del dado (joystick + botón)
**Estado actual: el juguete usa el firmware original y estático**
(`arduino/sketch_bluba_original.ino`, sin modificar), con umbrales fijos
(movimiento brusco > 0.6, clic rápido < 300 ms) — todavía **sin
personalizar por niño/a**.

Para ver sus alertas en tiempo real en el HTML **no hace falta backend ni
bridge**: la sección "Juguete en vivo" del HTML se conecta directo al
Arduino desde el propio navegador (Web Serial API) y muestra la alerta
apenas el Arduino la manda por Bluetooth/USB.

Requisitos de esta sección:
- Navegador **Chrome o Edge de escritorio** (Web Serial no existe en
  Firefox, Safari ni en navegadores móviles).
- El HC-06 ya pareado en el sistema operativo (Bluetooth → agregar
  dispositivo) para que aparezca como puerto serial.
- Si el botón "Conectar juguete" falla al abrir el archivo directo,
  sirve la carpeta con `python -m http.server` y ábrelo como
  `http://localhost:8000/propuesta-bluba-ml.html`.

## Para más adelante: personalización del juguete por niño/a

Ya está construido (aunque no en uso todavía) un modo donde el umbral de
"brusco"/"rápido" se calibra según el historial de juego de cada niño/a,
en vez de un valor fijo para todos:

- `arduino/sketch_bluba_personalizado.ino` — mismo joystick/botón, pero el
  umbral se recibe por Bluetooth (`CFG,T,...` / `CFG,D,...`) y el Arduino
  transmite la señal cruda todo el tiempo, no solo cuando alerta.
- `backend/sensores.py` — calcula ese umbral personalizado por niño/a con
  la misma lógica de baseline + shrinkage que usa el modelo de crisis
  (`backend/personalizacion.py`).
- `backend/bridge_bluetooth.py` — conecta el HC-06 con la API: al empezar
  la sesión le pide a `app.py` el umbral calibrado de ese niño/a y se lo
  baja al Arduino; mientras juega, reenvía cada evento al backend.

Cuando quieran activar este modo: flashear
`sketch_bluba_personalizado.ino` en vez del original, y correr
`bridge_bluetooth.py` en el celular/PC pareado con el HC-06. Todo el
detalle (protocolo de comandos, cálculo del umbral, diagrama de flujo)
está en `backend/README.md`.
