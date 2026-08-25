# Propuesta Bluba — ML de anticipación de crisis conductual

Datatón FICA UFRO × Bluba SpA. Contenido de esta carpeta:

```
propuesta-bluba/
├── propuesta-bluba-ml.html     ← front-end de la propuesta (ábrelo en el navegador)
└── backend/                    ← API + modelo + integración con el juguete
    ├── README.md                (instrucciones detalladas de instalación y uso)
    ├── requirements.txt          dependencias del servidor (Flask, sklearn, pandas...)
    ├── requirements-bridge.txt   dependencias del script puente Bluetooth
    ├── seed_dataset.py           genera la base de datos inicial (CSV)
    ├── base_bluba.csv            base de datos de ejemplo ya generada
    ├── personalizacion.py        baseline + shrinkage por niño/a (compartido)
    ├── modelo.py                 imputación MICE + Random Forest
    ├── sensores.py                procesamiento de señales del juguete
    ├── app.py                    API Flask (endpoints del registro y del sensor)
    ├── bridge_bluetooth.py       puente HC-06 (Arduino) -> API
    └── arduino/
        └── sketch_bluba.ino      firmware del dado (joystick + botón)
```

## Para empezar rápido

1. Abre `propuesta-bluba-ml.html` en el navegador — es la propuesta completa
   (contexto, pipeline, requisitos) con una demo interactiva al final.
2. Para que la demo prediga de verdad, levanta el backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   python seed_dataset.py     # ya viene un CSV de ejemplo, pero puedes regenerarlo
   python app.py              # API en http://localhost:5000
   ```
3. Detalles de la personalización por niño/a (sueño/ánimo) y de la
   integración con el juguete sensorial (Arduino + Bluetooth) están en
   `backend/README.md`.
