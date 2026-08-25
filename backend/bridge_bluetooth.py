"""
Puente Bluetooth <-> API Bluba.

Corre en el celular/PC que está PAREADO por Bluetooth con el HC-06 del
juguete (el HC-06 aparece como un puerto serial estándar una vez pareado:
COMx en Windows, /dev/rfcommX o /dev/tty.HC-06 en Linux/Mac).

Qué hace:
  1. Al iniciar una sesión, pide al backend el umbral YA CALIBRADO para el
     niño/a que va a jugar (GET /api/sensor/umbral/<usuario_id>) y se lo
     manda al Arduino ("CFG,T,..." / "CFG,D,...") para que alerte en tiempo
     real con SU propio umbral, no uno genérico.
  2. Escucha continuamente las líneas que manda el Arduino (movimientos y
     clics crudos) y las reenvía al backend (POST /api/sensor/evento), que
     las va acumulando para seguir afinando el baseline de ese niño/a.

Requiere:
    pip install pyserial requests

Uso:
    python bridge_bluetooth.py --puerto COM5 --usuario familia_demo_01
    python bridge_bluetooth.py --puerto /dev/rfcomm0 --usuario familia_demo_01 --api http://localhost:5000
"""
import argparse
import sys
import time

import requests
import serial


def calibrar_umbrales(api_url: str, usuario_id: str, conexion: serial.Serial):
    try:
        resp = requests.get(f"{api_url}/api/sensor/umbral/{usuario_id}", timeout=5)
        resp.raise_for_status()
        umbrales = resp.json()
    except requests.RequestException as e:
        print(f"[bridge] No se pudo obtener el umbral personalizado ({e}); "
              f"el Arduino seguirá con sus valores por defecto.")
        return

    conexion.write(f"CFG,T,{umbrales['umbral_movimiento']}\n".encode())
    time.sleep(0.1)
    conexion.write(f"CFG,D,{umbrales['umbral_clic_ms']}\n".encode())

    print(f"[bridge] Umbrales calibrados para '{usuario_id}': "
          f"movimiento={umbrales['umbral_movimiento']}, "
          f"clic_ms={umbrales['umbral_clic_ms']} "
          f"(basado en {umbrales['dias_sesion']} días de historial propio)")


def reenviar_evento(api_url: str, usuario_id: str, tipo: str, valor: float):
    try:
        requests.post(
            f"{api_url}/api/sensor/evento",
            json={"usuario_id": usuario_id, "tipo": tipo, "valor": valor, "timestamp": time.time()},
            timeout=3,
        )
    except requests.RequestException as e:
        print(f"[bridge] Aviso: no se pudo reenviar evento al backend ({e})")


def correr(puerto: str, usuario_id: str, api_url: str, baudrate: int = 9600):
    print(f"[bridge] Conectando a {puerto} ...")
    with serial.Serial(puerto, baudrate, timeout=1) as conexion:
        time.sleep(2)  # margen típico para que el HC-06 quede listo tras abrir el puerto
        calibrar_umbrales(api_url, usuario_id, conexion)

        print(f"[bridge] Escuchando eventos del juguete para '{usuario_id}'. Ctrl+C para salir.")
        while True:
            try:
                linea = conexion.readline().decode(errors="ignore").strip()
            except serial.SerialException as e:
                print(f"[bridge] Se perdió la conexión serial: {e}")
                break

            if not linea:
                continue

            partes = linea.split(",")
            tipo_msg = partes[0]

            if tipo_msg == "M" and len(partes) >= 2:
                magnitud = float(partes[1])
                reenviar_evento(api_url, usuario_id, "movimiento", magnitud)

            elif tipo_msg == "C":
                reenviar_evento(api_url, usuario_id, "clic", 1)

            elif tipo_msg == "ALERT_M":
                print(f"[bridge] ⚠️  Movimiento brusco (para este niño/a): {partes[1] if len(partes)>1 else ''}")

            elif tipo_msg == "ALERT_C":
                print("[bridge] ⚠️  Clic muy rápido (para este niño/a)")

            elif tipo_msg == "OK":
                print(f"[bridge] Arduino confirmó calibración: {linea}")

            else:
                print(f"[bridge] (sin procesar) {linea}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Puente Bluetooth (HC-06) -> API Bluba")
    parser.add_argument("--puerto", required=True, help="Puerto serial del HC-06, ej. COM5 o /dev/rfcomm0")
    parser.add_argument("--usuario", required=True, help="usuario_id del niño/a que está jugando ahora")
    parser.add_argument("--api", default="http://localhost:5000", help="URL base del backend Flask")
    args = parser.parse_args()

    try:
        correr(args.puerto, args.usuario, args.api)
    except KeyboardInterrupt:
        print("\n[bridge] Detenido por el usuario.")
        sys.exit(0)
