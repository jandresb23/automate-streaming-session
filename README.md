# Automatización de alistamiento de streaming

Automatiza las 11 etapas previas a iniciar una transmisión con VDO.Ninja
(captura desde móvil), OBS Studio (mezcla/gestión) y Facebook (servidor de
transmisión, perfil personal).

## Instalación

```bash
cd stream_automation
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

## Configuración

1. Copia `.env.example` como `.env`.
2. Completa los valores: contraseña del WebSocket de OBS, ruta al ejecutable
   de OBS, nombre de la escena y del Browser Source ya existentes, etc.
3. Habilita el WebSocket en OBS: **Herramientas → Configuración de WebSocket
   del servidor** → activar servidor + autenticación (ver contraseña en
   `.env`).

## Primer uso: guardar sesión de Facebook

Este paso se hace **una sola vez** (o cuando la sesión expire):

```bash
python setup_facebook_login.py
```

Se abrirá un navegador. Inicia sesión manualmente en tu cuenta de Facebook,
y cuando termines vuelve a la terminal y presiona ENTER. Esto guarda tus
cookies de sesión en `facebook_session.json` (excluido de git).

## Ejecutar el alistamiento

```bash
python main.py
```

Se abre una ventana con un campo **"Título de la sesión"** y un botón
**"Iniciar alistamiento"**. Escribe el título de esta transmisión (varía
cada vez, por eso se pide en la interfaz y no en `.env`) y presiona el botón.
Se ejecutan en orden las 11 etapas. En el paso 6 (escaneo de QR) aparecerá
un cuadro de confirmación: escanea con tu móvil y presiona OK para continuar.

## ⚠️ Advertencias importantes

- **Selectores de Facebook y VDO.Ninja**: ambas interfaces web pueden cambiar
  con el tiempo. Si un paso falla con un error de "no se encontró el botón/campo",
  usa `playwright codegen <url>` para inspeccionar la página actual y ajustar
  el selector correspondiente en `facebook_automation.py` o `vdoninja_automation.py`.
- **Términos de servicio de Facebook**: automatizar interacciones con la
  interfaz web de un perfil personal no es un uso oficialmente soportado por
  Meta. Un uso razonable (una sola sesión, acciones espaciadas, sin volumen
  alto) reduce el riesgo, pero no lo elimina. Si en algún momento migras a
  una Página de Facebook, se recomienda usar la Graph API oficial en su lugar.
- **`facebook_session.json` y `.env` son credenciales**: no los compartas ni
  los subas a ningún repositorio. Ambos ya están excluidos en `.gitignore`.
- **Formato de grabación (Matroska)**: el parámetro interno usado
  (`RecFormat2`) corresponde a versiones recientes de OBS. Si tu versión es
  distinta, revisa el mensaje de error — indica cómo ajustarlo.

## Estructura del proyecto

```
stream_automation/
├── main.py                     # Interfaz (botón único) y punto de entrada
├── orchestrator.py             # Orquesta las 11 etapas en orden
├── obs_controller.py           # Facade sobre obsws-python
├── vdoninja_automation.py      # Facade sobre Playwright para VDO.Ninja
├── facebook_automation.py      # Facade sobre Playwright para Facebook
├── setup_facebook_login.py     # Script de un solo uso para guardar sesión
├── config.py                   # Carga y valida parámetros desde .env
├── logger.py                   # Logging centralizado
├── requirements.txt
├── .env.example
└── .gitignore
```
