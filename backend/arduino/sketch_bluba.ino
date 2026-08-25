/*
  Dado sensorial Bluba — joystick + botón vía Bluetooth (HC-06)

  CAMBIOS respecto a la versión original:
  1) thresholdMovimiento y thresholdDobleClic dejan de ser fijos en el código
     (antes eran iguales para todos los niños). Ahora son variables que se
     pueden actualizar en caliente por Bluetooth con un comando de
     configuración, enviado por el script puente (bridge_bluetooth.py) al
     empezar cada sesión, con el umbral YA CALIBRADO para ese niño/a
     (ver backend/sensores.py -> calcular_umbrales_personalizados).
     El MISMO Arduino/firmware sirve para todos los niños; lo único que
     cambia es el número que se le manda.

  2) Además de las alertas ("¡ALERTA! ..."), el Arduino ahora transmite
     SIEMPRE la magnitud cruda del movimiento y cada clic del botón
     (no solo cuando supera el umbral). Sin esto, el backend nunca podría
     aprender cuál es el patrón "normal" de cada niño para calcular su
     propio umbral — necesita ver también los movimientos suaves.

  Protocolo por Bluetooth (líneas de texto separadas por '\n'):
    Arduino -> host:
      M,<magnitud>,<millis>        muestra de movimiento (siempre)
      C,<millis>                   clic del botón (siempre)
      ALERT_M,<magnitud>           movimiento superó el umbral ACTUAL
      ALERT_C                      doble clic rápido superó el umbral ACTUAL
    host -> Arduino:
      CFG,T,<float>                fija thresholdMovimiento (ej: CFG,T,0.42)
      CFG,D,<int>                  fija thresholdDobleClic en ms (ej: CFG,D,260)
*/

#include <ezButton.h>
#include <SoftwareSerial.h>

// Definición de pines del Joystick
#define VRX_PIN  A0
#define VRY_PIN  A1
#define SW_PIN   2

// Definición de pines para el módulo Bluetooth HC-06
#define BT_RX 10
#define BT_TX 11

SoftwareSerial BTSerial(BT_RX, BT_TX);
ezButton button(SW_PIN);

// Variables del Joystick
float xValue = 0;
float yValue = 0;
float lastXValue = 0;
float lastYValue = 0;

// Variables para control de tiempo
unsigned long lastTime = 0;
unsigned long lastPressTime = 0;

// --- Umbrales de sensibilidad ---
// Ya NO son "const": arrancan con un valor por defecto razonable (el mismo
// que usaba el sketch original) y se sobrescriben con el umbral
// personalizado que calcula el backend para el niño/a que está jugando.
float thresholdMovimiento = 0.6;     // "brusco" por defecto hasta calibrar
int thresholdDobleClic = 300;        // "rápido" por defecto hasta calibrar

const int updateInterval = 50;       // leer el joystick cada 50ms
const float pisoRuido = 0.03;        // no transmitir micro-jitter irrelevante

// Buffer para leer comandos entrantes por Bluetooth línea por línea
String comandoEntrante = "";

void setup() {
  Serial.begin(9600);
  BTSerial.begin(9600);

  button.setDebounceTime(50);

  Serial.println("Iniciando sistema...");
  BTSerial.println("Bluetooth conectado y listo.");
}

void loop() {
  button.loop();
  leerComandosBluetooth();

  unsigned long currentTime = millis();

  // 1. DETECCIÓN DE PULSACIONES RÁPIDAS (clic del botón)
  if (button.isPressed()) {
    unsigned long timeSinceLastPress = currentTime - lastPressTime;

    // Siempre se transmite el clic crudo (para que el backend aprenda
    // el ritmo habitual de clics de este niño/a).
    BTSerial.print("C,");
    BTSerial.println(currentTime);

    // Alerta en tiempo real usando el umbral YA CALIBRADO para este niño/a.
    if (timeSinceLastPress > 50 && timeSinceLastPress <= (unsigned long)thresholdDobleClic) {
      Serial.println("¡ALERTA! Pulsación de botón muy rápida.");
      BTSerial.println("ALERT_C");
    }

    lastPressTime = currentTime;
  }

  // 2. LECTURA Y TRANSMISIÓN DEL MOVIMIENTO
  if (currentTime - lastTime >= updateInterval) {
    xValue = (analogRead(VRX_PIN) - 560.0) / 560.0;
    yValue = (analogRead(VRY_PIN) - 560.0) / 560.0;

    float deltaX = abs(xValue - lastXValue);
    float deltaY = abs(yValue - lastYValue);
    float magnitud = sqrt(deltaX * deltaX + deltaY * deltaY);

    // Se transmite la muestra cruda casi siempre (salvo micro-jitter),
    // sin importar si supera o no el umbral — esto es lo que le permite al
    // backend construir el baseline personal de cada niño/a.
    if (magnitud > pisoRuido) {
      BTSerial.print("M,");
      BTSerial.print(magnitud, 3);
      BTSerial.print(",");
      BTSerial.println(currentTime);
    }

    // Alerta en tiempo real usando el umbral YA CALIBRADO para este niño/a.
    if (magnitud > thresholdMovimiento) {
      Serial.print("¡ALERTA! Movimiento brusco detectado. Magnitud:");
      Serial.println(magnitud);
      BTSerial.print("ALERT_M,");
      BTSerial.println(magnitud, 3);
    }

    lastXValue = xValue;
    lastYValue = yValue;
    lastTime = currentTime;
  }
}

// Lee comandos "CFG,T,<float>" / "CFG,D,<int>" que llegan por Bluetooth
// desde el script puente para calibrar los umbrales de ESTE niño/a.
void leerComandosBluetooth() {
  while (BTSerial.available() > 0) {
    char c = BTSerial.read();
    if (c == '\n') {
      procesarComando(comandoEntrante);
      comandoEntrante = "";
    } else if (c != '\r') {
      comandoEntrante += c;
    }
  }
}

void procesarComando(String linea) {
  linea.trim();
  if (!linea.startsWith("CFG,")) return;

  int primeraComa = linea.indexOf(',', 4);
  if (primeraComa == -1) return;

  String tipo = linea.substring(4, primeraComa);
  String valorStr = linea.substring(primeraComa + 1);

  if (tipo == "T") {
    thresholdMovimiento = valorStr.toFloat();
    Serial.print("Umbral de movimiento calibrado a: ");
    Serial.println(thresholdMovimiento);
    BTSerial.print("OK,T,");
    BTSerial.println(thresholdMovimiento, 3);
  } else if (tipo == "D") {
    thresholdDobleClic = valorStr.toInt();
    Serial.print("Umbral de clic rapido calibrado a: ");
    Serial.println(thresholdDobleClic);
    BTSerial.print("OK,D,");
    BTSerial.println(thresholdDobleClic);
  }
}
