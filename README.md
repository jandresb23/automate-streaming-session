# Automatización de alistamiento de streaming

Automatiza las etapas previas a iniciar una transmisión con VDO.Ninja
(captura desde móvil), OBS Studio (mezcla/gestión) y **YouTube** (servidor
de transmisión, vía su API oficial — no usa navegador ni automatización
de interfaz para esta parte).

> **Nota**: el proyecto incluye también `facebook_automation.py` y
> `setup_facebook_login.py` de un intento anterior con Facebook como
> servidor de transmisión. Quedan sin usar por ahora (no están conectados
> al flujo principal) por si se retoma esa integración más adelante.

## Instalación

```bash
cd stream_automation
python -m venv .venv
source .venv/Scripts/activate   # Git Bash en Windows
pip install -r requirements.txt
playwright install chromium
```

## Configuración de YouTube (API oficial)

1. En [Google Cloud Console](https://console.cloud.google.com/), en tu
   proyecto, habilita la **YouTube Data API v3**.
2. Ve a **Credenciales → Crear credenciales → ID de cliente OAuth**, tipo
   **"Aplicación de escritorio"**, y descarga el archivo JSON resultante.
3. Copia `.env.example` como `.env` y completa:
   - `YOUTUBE_CLIENT_SECRETS_PATH`: ruta al JSON que acabas de descargar.
   - El resto de variables de OBS y VDO.Ninja, como ya las tenías.
4. Ejecuta la autorización única:
   ```bash
   python setup_youtube_auth.py
   ```
   Se abrirá tu navegador pidiéndote iniciar sesión con la cuenta de Google
   dueña del canal y autorizar el acceso. El token queda guardado en
   `YOUTUBE_TOKEN_PATH` (por defecto `youtube_token.json`, excluido de git).

## Configuración de OBS

Habilita el WebSocket (Herramientas → Configuración de WebSocket del
servidor) y completa los valores correspondientes en `.env`
(`OBS_HOST`, `OBS_PORT`, `OBS_PASSWORD`, etc.). El formato de grabación
debe estar en modo **Avanzado** (Ajustes → Salida → Modo = Avanzado) para
que la validación automática de formato Matroska funcione correctamente.

## Ejecutar el alistamiento

```bash
python main.py
```

Se abre una ventana con un campo **"Título de la sesión"** y un botón
**"Iniciar alistamiento"**. Escribe el título y presiona el botón. Se
ejecutan en orden las etapas: creación de la transmisión en YouTube,
apertura de VDO.Ninja, configuración de OBS, y finalmente el paso a "en
vivo" en YouTube una vez que detecta la señal entrante.

## ⚠️ Advertencias importantes

- **Selectores de VDO.Ninja**: su interfaz web puede cambiar con el tiempo.
  Si el paso 4 falla, usa `playwright codegen https://vdo.ninja/` para
  verificar el selector actual y ajustar `vdoninja_automation.py`.
- **`youtube_token.json`, `client_secret*.json` y `.env` son credenciales**:
  no los compartas ni los subas a ningún repositorio. Ya están excluidos
  en `.gitignore`.
- **Formato de grabación (Matroska)**: los nombres de parámetro internos
  de OBS pueden variar según versión. Si `validate_recording_format` falla,
  el mensaje de error te guía para depurarlo con `debug_obs_signature.py`.
- **`set_stream_destination`**: al igual que con el formato de grabación,
  si esta llamada falla por un argumento inesperado, la firma exacta puede
  variar según tu versión de `obsws-python`; usa el mismo enfoque de
  `debug_obs_signature.py` (adaptado a `set_stream_service_settings`) para
  confirmarla.

## Estructura del proyecto

```
stream_automation/
├── main.py                       # Interfaz (botón único) y punto de entrada
├── orchestrator.py               # Orquesta las etapas en orden
├── obs_controller.py             # Facade sobre obsws-python
├── vdoninja_automation.py        # Facade sobre Playwright para VDO.Ninja
├── youtube_automation.py         # Facade sobre la API de YouTube Live Streaming
├── setup_youtube_auth.py         # Script de un solo uso: autorización OAuth
├── facebook_automation.py        # (Sin usar por ahora) integración con Facebook
├── setup_facebook_login.py       # (Sin usar por ahora) login de Facebook
├── config.py                     # Carga y valida parámetros desde .env
├── logger.py                     # Logging centralizado
├── test_obs.py                   # Script de prueba aislado para OBS
├── debug_obs_signature.py        # Utilidad de diagnóstico para obsws-python
├── requirements.txt
├── .env.example
└── .gitignore
```
