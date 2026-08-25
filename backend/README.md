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

## Personalización por niño/a sin un modelo por niño/a

En vez de entrenar un modelo distinto para cada niño o niña (costoso e
inviable con poco historial por persona), se personaliza el **input**, no
el modelo:

- Para cada `usuario_id`, `modelo.calcular_baselines()` calcula su propia
  media y desviación estándar histórica en cada variable (p.ej. cuántas
  horas duerme habitualmente).
- Cada registro se transforma también en un **z-score personal**:
  `(valor_de_hoy - media_del_niño) / std_del_niño`. Así, "durmió 6 horas"
  puede ser una señal de riesgo para un niño que duerme 9h habitualmente,
  y neutra para otro que siempre duerme 6h.
- El Random Forest recibe **tanto el valor crudo como el z-score** como
  columnas separadas (no hace falta elegir uno u otro: los árboles no son
  sensibles a la escala).
- **Cold start**: si un niño/a tiene poco historial propio, su baseline se
  encoge (shrinkage) hacia el promedio poblacional — con pocos días pesa
  casi todo la población, con 20-30 días pesa casi todo su propio patrón
  (parámetro `K_SHRINKAGE` en `modelo.py`). La respuesta de la API incluye
  esto en `completeness_note` cuando aplica, y la `confidence` sube a
  medida que el niño/a acumula más días registrados.
- Simplificación de prototipo: el baseline usa todo el historial disponible
  del niño/a (no solo los días anteriores al registro evaluado), lo que
  introduce una leve fuga de información en el entrenamiento. Para
  producción conviene una versión expansiva/rolling que solo mire el
  pasado de cada fila.
- Esta lógica vive en `personalizacion.py`, compartida entre `modelo.py`
  (variables del registro diario) y `sensores.py` (señales del juguete) —
  la misma idea de baseline+shrinkage sirve para ambas fuentes de datos.

## Juguete sensorial (dado con joystick/botón, Arduino + HC-06)

**Estado actual: en uso el firmware original y estático**
(`arduino/sketch_bluba_original.ino`, sin ninguna modificación), con
umbrales fijos (movimiento brusco > 0.6, clic rápido < 300 ms) — todavía
sin personalizar por niño/a. Para ver sus alertas en tiempo real basta con
la sección "Juguete en vivo" del HTML (Web Serial, sin backend ni bridge;
ver el README raíz del proyecto para los requisitos de navegador).

Lo que sigue describe el modo **personalizado**, ya construido pero no en
uso todavía: mismo principio aplicado a las señales del dado — un umbral
fijo de "movimiento brusco" no tiene sentido si un niño juega naturalmente
más fuerte que otro. En vez de tener un firmware por niño, un solo firmware
(`arduino/sketch_bluba_personalizado.ino`) recibe el umbral calibrado para
quien esté jugando en ese momento.

```
 Arduino (sketch_bluba_personalizado.ino) bridge_bluetooth.py                Backend Flask
 ─────────────────────────                ────────────────────               ─────────────
 lee joystick/botón                                                          
 SIEMPRE transmite la señal    ──BT──▶    escucha el puerto serial  ──HTTP──▶ POST /api/sensor/evento
 cruda (M,<mag>,<ms> / C,<ms>)             del HC-06 y reenvía cada           (guarda en sensores_bluba.csv)
                                           línea al backend

 también alerta en vivo con     ◀──BT──   al iniciar la sesión pide  ◀──HTTP── GET /api/sensor/umbral/<id>
 el umbral ACTUAL (ALERT_M/C)             el umbral de ESE niño/a               (calcula el baseline personal
                                          y se lo manda al Arduino              de ese niño con sensores.py)
                                          como "CFG,T,.." / "CFG,D,.."
```

- `arduino/sketch_bluba_personalizado.ino`: ya no tiene los umbrales fijos en el código
  (`thresholdMovimiento=0.6`, `thresholdDobleClic=300`). Ahora son variables
  que se actualizan en caliente por Bluetooth (`CFG,T,<valor>` /
  `CFG,D,<valor>`), y el Arduino transmite la señal cruda TODO el tiempo
  (no solo cuando supera el umbral) — sin eso el backend nunca podría
  aprender cuál es el patrón normal de cada niño/a.
- `sensores.py`: agrega los eventos crudos por día/niño (percentil 90 de la
  intensidad de movimiento, intervalo promedio entre clics) y calcula, con
  la misma lógica de `personalizacion.py`, el umbral que corresponde
  SOLO a ese niño/a (`calcular_umbrales_personalizados`). Un niño/a sin
  historial recibe los valores por defecto del firmware original.
- `bridge_bluetooth.py`: corre en el celular/PC pareado con el HC-06 (no en
  este backend). Al iniciar la sesión, pide el umbral calibrado y se lo baja
  al Arduino; mientras dure la sesión, reenvía cada línea que llega del
  juguete al backend. Requiere `pip install -r requirements-bridge.txt`.
- `sensor_resumen(usuario_id, fecha)` deja listo cuántos "movimientos
  bruscos" y "clics rápidos" tuvo el niño/a hoy, YA evaluados contra su
  propio umbral — pensado para pre-completar `desregulaciones_previas` en
  el registro familiar con datos objetivos del juguete, en vez de pedírselo
  a la familia, lo que ayuda directamente al requisito de Bluba de reducir
  la carga de registro.
- Limitación conocida del prototipo: el umbral se recalcula sobre TODO el
  historial de sesiones del niño/a (no distingue día por día en tiempo
  real dentro de una misma sesión). Con muy pocos niños de referencia (como
  en una demo), la desviación poblacional puede ser grande y "arrastrar"
  el umbral de cada niño hacia arriba; con más niños en la base de datos
  esto se estabiliza.



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
