# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bless",
#     "bleak",
#     "pysetupdi @ git+https://github.com/gwangyi/pysetupdi",
# ]
# ///

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Shims for Windows BLE support in Python 3.13
if sys.platform == "win32":
    import types
    try:
        import winrt
        import winrt.windows.devices.bluetooth
        import winrt.windows.devices.bluetooth.genericattributeprofile
        import winrt.windows.devices.bluetooth.advertisement
        import winrt.windows.foundation
        import winrt.windows.storage.streams
        
        sys.modules['bleak_winrt'] = winrt
        sys.modules['bleak_winrt.windows'] = winrt.windows
        sys.modules['bleak_winrt.windows.devices'] = winrt.windows.devices
        sys.modules['bleak_winrt.windows.devices.bluetooth'] = winrt.windows.devices.bluetooth
        sys.modules['bleak_winrt.windows.devices.bluetooth.genericattributeprofile'] = winrt.windows.devices.bluetooth.genericattributeprofile
        sys.modules['bleak_winrt.windows.devices.bluetooth.advertisement'] = winrt.windows.devices.bluetooth.advertisement
        sys.modules['bleak_winrt.windows.foundation'] = winrt.windows.foundation
        sys.modules['bleak_winrt.windows.storage'] = winrt.windows.storage
        sys.modules['bleak_winrt.windows.storage.streams'] = winrt.windows.storage.streams
    except ImportError:
        pass

    try:
        import bleak.backends.service
        import bleak.backends.characteristic
        
        _handle_counter = 1
        class MockBleakGATTServiceWinRT(bleak.backends.service.BleakGATTService):
            def __init__(self, *args, **kwargs):
                uuid = args[0] if args else (kwargs.get('uuid') or '00000000-0000-0000-0000-000000000000')
                self.obj = None
                self._handle = 0
                if not hasattr(self, '_uuid'):
                    self._uuid = str(uuid)
                self._characteristics = {}

        class MockBleakGATTCharacteristicWinRT(bleak.backends.characteristic.BleakGATTCharacteristic):
            def __init__(self, *args, **kwargs):
                obj = kwargs.get('obj') or (args[0] if args else None)
                self.obj = obj
                global _handle_counter
                self._handle = _handle_counter
                _handle_counter += 1
                if not hasattr(self, '_uuid'):
                    self._uuid = '00000000-0000-0000-0000-000000000000'
                self._properties = []
                self._max_write_without_response_size = kwargs.get('max_write_without_response_size') or 128
                self._service = None
                self._descriptors = {}

        bleak_winrt_service_mock = types.ModuleType('bleak.backends.winrt.service')
        bleak_winrt_service_mock.BleakGATTServiceWinRT = MockBleakGATTServiceWinRT
        sys.modules['bleak.backends.winrt.service'] = bleak_winrt_service_mock
        
        bleak_winrt_char_mock = types.ModuleType('bleak.backends.winrt.characteristic')
        bleak_winrt_char_mock.BleakGATTCharacteristicWinRT = MockBleakGATTCharacteristicWinRT
        sys.modules['bleak.backends.winrt.characteristic'] = bleak_winrt_char_mock
    except Exception:
        pass

    # Patch BlessServerWinRT start method
    try:
        from bless.backends.winrt.server import BlessServerWinRT
        from winrt.windows.devices.bluetooth.genericattributeprofile import GattServiceProviderAdvertisingParameters
        
        async def patched_start(self: BlessServerWinRT, **kwargs):
            if self._name_overwrite:
                self._adapter.set_local_name(self.name)
            adv_parameters = GattServiceProviderAdvertisingParameters()
            adv_parameters.is_discoverable = True
            adv_parameters.is_connectable = True
            for uuid, service in self.services.items():
                if hasattr(service.service_provider, 'start_advertising_with_parameters'):
                    service.service_provider.start_advertising_with_parameters(adv_parameters)
                else:
                    try:
                        service.service_provider.start_advertising(adv_parameters)
                    except TypeError:
                        service.service_provider.start_advertising()
            self._advertising = True
            self._advertising_started.set()

        BlessServerWinRT.start = patched_start
    except Exception:
        pass

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
except ImportError as ie:
    import traceback
    print(f"[WARN] Error al importar 'bless': {ie}")
    traceback.print_exc()
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
        
        # Actualizar valores en los objetos de característica
        weight_char = ble_server.get_characteristic(WEIGHT_CHAR_UUID)
        if weight_char:
            weight_char.value = peso_bytes
            
        height_char = ble_server.get_characteristic(HEIGHT_CHAR_UUID)
        if height_char:
            height_char.value = estatura_bytes
        
        # Disparar notificaciones a los clientes suscritos
        ble_server.update_value(SERVICE_UUID, WEIGHT_CHAR_UUID)
        ble_server.update_value(SERVICE_UUID, HEIGHT_CHAR_UUID)
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
            service_uuid=SERVICE_UUID,
            char_uuid=WEIGHT_CHAR_UUID,
            properties=GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
            permissions=GATTAttributePermissions.readable,
            value=bytearray(str(device_data["peso"]).encode('utf-8'))
        )
        
        # Registrar Característica de Estatura (Lectura + Notificaciones)
        await ble_server.add_new_characteristic(
            service_uuid=SERVICE_UUID,
            char_uuid=HEIGHT_CHAR_UUID,
            properties=GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
            permissions=GATTAttributePermissions.readable,
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
