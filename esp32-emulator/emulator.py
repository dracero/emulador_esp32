# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bless",
# ]
# ///

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# UUIDs de Servicio y Características (Estándar de 128 bits)
SERVICE_UUID = "12345678-1234-5678-1234-567812345678"
WEIGHT_CHAR_UUID = "12345678-1234-5678-1234-567812345679"
HEIGHT_CHAR_UUID = "12345678-1234-5678-1234-56781234567a"

# Estado local del dispositivo emulado (ESP32)
device_data = {
    "peso": 75.0,
    "estatura": 1.75
}

# Configuración de Bluetooth BLE
BLE_SUPPORTED = False
ble_server = None
ble_active = False
loop = None

try:
    from bless import (
        BlessServer,
        GATTCharacteristicProperties,
        GATTAttributePermissions
    )
    import asyncio
    BLE_SUPPORTED = True
except ImportError:
    print("[WARN] Librería 'bless' no encontrada. El soporte Bluetooth BLE no estará disponible.")
    print("       Puedes instalarla usando: pip install bless")
    print("       El emulador continuará funcionando en modo Wi-Fi (HTTP API).")
    BLE_SUPPORTED = False

# Handler para el servidor HTTP local
class EmulatorHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Desactivar logs de peticiones HTTP en consola para no ensuciar la salida
        pass

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # API para consultar los datos del sensor
        if self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(device_data).encode('utf-8'))
        
        # Servir el Panel de Control Web
        elif self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            script_dir = os.path.dirname(os.path.realpath(__file__))
            html_path = os.path.join(script_dir, "control-panel", "index.html")
            
            if os.path.exists(html_path):
                with open(html_path, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                fallback_html = """
                <!DOCTYPE html>
                <html lang="es">
                <head>
                    <meta charset="UTF-8">
                    <title>ESP32 Emulator Panel - Fallback</title>
                    <style>
                        body { font-family: sans-serif; background: #0f172a; color: #fff; padding: 2rem; }
                    </style>
                </head>
                <body>
                    <h1>ESP32 Emulator</h1>
                    <p>Archivo 'control-panel/index.html' no encontrado en el directorio.</p>
                </body>
                </html>
                """
                self.wfile.write(fallback_html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        # API para actualizar el peso y estatura desde el panel de control web
        if self.path == '/api/data':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                if "peso" in data:
                    device_data["peso"] = float(data["peso"])
                if "estatura" in data:
                    device_data["estatura"] = float(data["estatura"])
                
                print(f"[HTTP PANEL] Peso={device_data['peso']} kg | Estatura={device_data['estatura']} m")
                
                # Actualizar los valores en el servidor BLE si está activo
                if ble_active and ble_server and loop:
                    update_ble_data()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "data": device_data}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

# Función para encolar la actualización BLE en el event loop de asyncio
def update_ble_data():
    global loop, ble_server
    if not BLE_SUPPORTED or not ble_server or not loop:
        return
    
    asyncio.run_coroutine_threadsafe(
        update_ble_async(),
        loop
    )

async def update_ble_async():
    global ble_server
    try:
        peso_bytes = bytearray(str(device_data["peso"]).encode('utf-8'))
        estatura_bytes = bytearray(str(device_data["estatura"]).encode('utf-8'))
        
        # Actualizar valores
        ble_server.write_value(WEIGHT_CHAR_UUID, peso_bytes)
        ble_server.write_value(HEIGHT_CHAR_UUID, estatura_bytes)
        
        # Disparar notificaciones a los clientes suscritos
        await ble_server.update_value(SERVICE_UUID, WEIGHT_CHAR_UUID)
        await ble_server.update_value(SERVICE_UUID, HEIGHT_CHAR_UUID)
        print(f"[BLE ANUNCIANDO] Peso={device_data['peso']} | Estatura={device_data['estatura']} (Notificado)")
    except Exception as e:
        print(f"[BLE ERROR] Fallo al actualizar valores GATT: {e}")

# Servidor HTTP en hilo secundario
def start_http_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, EmulatorHTTPHandler)
    print("[HTTP] Servidor iniciado en http://localhost:8080")
    print("[HTTP] Sirviendo panel de control y endpoints de datos localmente.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

# Servidor BLE en el hilo principal (requiere event loop de asyncio)
async def start_ble_server():
    global ble_server, ble_active, loop
    loop = asyncio.get_event_loop()
    
    print("[BLE] Inicializando Servidor GATT BLE...")
    ble_server = BlessServer(name="ESP32-Salud-Emulator")
    
    try:
        # Registrar Servicio
        await ble_server.add_new_service(SERVICE_UUID)
        
        # Registrar Característica de Peso (Lectura + Notificaciones)
        await ble_server.add_new_characteristic(
            SERVICE_UUID,
            WEIGHT_CHAR_UUID,
            GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
            GATTAttributePermissions.readable,
            value=bytearray(str(device_data["peso"]).encode('utf-8'))
        )
        
        # Registrar Característica de Estatura (Lectura + Notificaciones)
        await ble_server.add_new_characteristic(
            SERVICE_UUID,
            HEIGHT_CHAR_UUID,
            GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
            GATTAttributePermissions.readable,
            value=bytearray(str(device_data["estatura"]).encode('utf-8'))
        )
        
        await ble_server.start()
        ble_active = True
        print(f"[BLE] Servidor BLE iniciado con éxito.")
        print(f"      Nombre del dispositivo: 'ESP32-Salud-Emulator'")
        print(f"      UUID Servicio: {SERVICE_UUID}")
        print(f"      UUID Peso Char: {WEIGHT_CHAR_UUID}")
        print(f"      UUID Estatura Char: {HEIGHT_CHAR_UUID}")
        
        # Mantener el loop corriendo
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"[BLE ERROR] Fallo al iniciar el Bluetooth BLE: {e}")
        print("[BLE INFO] El emulador continuará funcionando sólo en modo Wi-Fi (HTTP).")
        ble_active = False
        while True:
            await asyncio.sleep(1)

def main():
    # 1. Iniciar servidor HTTP en un hilo secundario daemon
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # 2. Iniciar Bluetooth BLE en el hilo principal
    if BLE_SUPPORTED:
        try:
            asyncio.run(start_ble_server())
        except KeyboardInterrupt:
            print("\nDeteniendo emulador...")
    else:
        print("[INFO] Bluetooth BLE no está disponible. Corriendo en modo exclusivo Wi-Fi (HTTP).")
        print("       Presiona Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDeteniendo emulador...")

if __name__ == '__main__':
    main()
