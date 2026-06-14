# Sistema de Monitoreo de Salud: Emulación ESP32 & App Móvil

Este proyecto integra un emulador de ESP32 por software (Python), una aplicación móvil en React Native (Expo) y un servidor de almacenamiento en la nube (Astro.js + MongoDB Atlas).

---

## 🚀 Guía de Inicio Rápido

Sigue estos pasos en tu computadora (PC Linux) para levantar todos los servicios:

### 1. Iniciar Backend y Emulador simultáneamente (Astro.js + Python uv)
Ahora puedes iniciar tanto el backend (Astro.js) como el emulador de ESP32 con un solo comando en la raíz del proyecto. El emulador Python se ejecutará automáticamente utilizando `uv` gestionando de manera transparente sus dependencias (como `bless`).
```bash
npm run dev
```
* **Acceso local Backend:** `http://localhost:4321`
* **Acceso local Emulador (Panel de Control):** `http://localhost:8080` (abre esto en el navegador de tu PC para ingresar los valores de peso/estatura y presionar "Transmitir").

### 2. Iniciar la App Móvil (React Native + Expo)
Compila y sirve la aplicación en tu celular a través de Expo Go.
```bash
cd mobile-app
ELECTRON_DISABLE_SANDBOX=1 npm run start
```
* **Acceso:** Escanea el código QR que aparece en la consola usando la app **Expo Go** en tu celular.

---

## 🛠️ Diagnóstico de Conexión (¿Por qué no conecta?)

Si la app en tu celular se queda en **"Buscando..."** o da error de conexión al ingresar la IP de tu PC, realiza esta prueba de descarte:

### Prueba de Oro: Prueba el navegador de tu celular
1. Asegúrate de que el celular y la PC estén en la **misma red Wi-Fi**.
2. Identifica la IP local de tu PC Linux (en tu terminal Metro se ve que es **`192.168.0.110`**).
3. Abre el **navegador web de tu celular** (Chrome/Safari) e intenta entrar a esta dirección:
   👉 **`http://192.168.0.110:8080`**

#### Resultados de la prueba:

* 🔴 **¿No carga en el celular (se queda cargando o da error de conexión)?**
  Significa que tu celular no tiene acceso físico a la PC. Las causas comunes son:
  1. **Firewall en Linux bloqueando la conexión:** El firewall de Linux bloquea las conexiones entrantes por seguridad. Desactívalo temporalmente en tu PC ejecutando en la terminal:
     ```bash
     sudo ufw disable
     ```
     *(O abre los puertos específicos: `sudo ufw allow 8080/tcp && sudo ufw allow 4321/tcp`)*.
  2. **Aislamiento de AP en el Router (AP Isolation):** Algunos routers de internet impiden que los dispositivos conectados por Wi-Fi se comuniquen entre sí (por ejemplo, redes de invitados o corporativas). Asegúrate de estar en una red local común.

* 🟢 **¿Sí carga el Panel de Control en el navegador del celular pero la App sigue sin conectar?**
  Significa que la red está bien, pero el sistema operativo de tu celular está bloqueando las conexiones HTTP inseguras (sin SSL/HTTPS) dentro de la aplicación de Expo Go.
   * **Solución rápida:** En `mobile-app/App.js`, las peticiones HTTP locales se realizan a través de `fetch()`. En algunos modelos de celular con configuraciones estrictas de seguridad de red, la app requiere que uses la dirección IP de red de forma directa. Asegúrate de escribir exactamente la IP **`192.168.0.110`** sin espacios ni caracteres adicionales en la app.

---

## 📱 Compilación e Instalación Standalone (APK para Producción)

Si realizas cambios en el código de React Native (`App.js`) y deseas volver a generar el archivo APK instalable independiente para tu celular, sigue estas instrucciones:

### 1. Compilar el APK de Producción (Release)
Ejecuta el siguiente comando desde la raíz del proyecto para compilar utilizando el SDK y el JDK local que configuramos:

```bash
cd mobile-app/android
JAVA_HOME=~/Android/jdk-17 ANDROID_HOME=~/Android/Sdk ./gradlew assembleRelease
```

* El archivo APK resultante se generará en:
  `mobile-app/android/app/build/outputs/apk/release/app-release.apk`

### 2. Transferir e Instalar en tu Celular
1. Transfiere el archivo `app-release.apk` a tu teléfono (por cable USB, subiéndolo a Google Drive, o enviándotelo por WhatsApp/Telegram).
2. En tu celular, abre el archivo `.apk` para iniciar la instalación.
3. Si Android te advierte sobre "aplicaciones desconocidas", selecciona **Ajustes** en la alerta y activa **Permitir desde esta fuente**.
4. Completa la instalación. Ahora tendrás la aplicación nativa instalada de forma permanente.

---

## 🏃 Guía de Uso del Sistema Real (Paso a Paso)

Para poner en marcha todo el sistema de manera integrada:

1. **Levantar el Backend y el Emulador ESP32:**
   En la raíz del proyecto, ejecuta:
   ```bash
   npm run dev
   ```
   *Esto iniciará la base de datos, el panel web del backend en `http://localhost:4321` y el panel del emulador en `http://localhost:8080`. Además, `uv` resolverá automáticamente las dependencias del emulador Python.*

3. **Ejecutar la App en tu Celular:**
   - Abre la aplicación **Control de Salud** instalada en tu teléfono.
   - Asegúrate de que el celular y la PC estén en la **misma red Wi-Fi**.
   - En la app, ingresa la IP local de tu PC (ej. `192.168.0.110`).
   - Verás cómo el estado cambia a **Conectado** y los campos de **PESO** y **ESTATURA** se actualizan en tiempo real con los valores del emulador.

4. **Enviar los Registros Médicos:**
   - En la app, ingresa el **DNI** y **Edad** del paciente.
   - Presiona **Guardar en MongoDB Atlas**.
   - Los datos se enviarán inmediatamente al backend y se registrarán de forma segura en la base de datos en la nube. Puedes corroborar el registro abriendo el panel web del backend en `http://localhost:4321`.

