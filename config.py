"""
Configuración centralizada del proyecto.

Todos los valores sensibles o dependientes del entorno (contraseñas, rutas,
nombres de escena, textos de botones) viven en el archivo `.env` y NO en el
código fuente. Esto permite:
  - Cambiar de equipo/configuración de OBS sin tocar el código.
  - Evitar credenciales expuestas en el repositorio.
"""

from dataclasses import dataclass
from pathlib import Path
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _require(var_name: str) -> str:
    """Obtiene una variable de entorno obligatoria o detiene la ejecución
    con un mensaje claro, en vez de fallar más adelante con un error críptico."""
    value = os.getenv(var_name)
    if not value:
        sys.exit(
            f"[CONFIG] Falta la variable obligatoria '{var_name}' en tu archivo .env. "
            f"Revisa .env.example como referencia."
        )
    return value


@dataclass(frozen=True)
class OBSConfig:
    host: str
    port: int
    password: str
    executable_path: Path
    scene_name: str
    browser_source_name: str
    recording_format: str
    startup_wait_seconds: int


@dataclass(frozen=True)
class VDONinjaConfig:
    url: str
    invite_button_text: str


@dataclass(frozen=True)
class YouTubeConfig:
    # Ruta al archivo client_secret.json descargado desde Google Cloud
    # Console (credencial OAuth de tipo "Aplicación de escritorio").
    client_secrets_path: Path
    # Ruta donde se guarda el token ya autorizado tras el primer login
    # (se genera automáticamente con setup_youtube_auth.py).
    token_path: Path
    # Segundos máximos a esperar a que YouTube detecte la señal entrante
    # de OBS antes de intentar pasar el broadcast a "live".
    stream_active_timeout_seconds: int
    # Nota: la visibilidad ('public'/'private') ya NO se define aquí.
    # Se selecciona cada vez en la ventana de la aplicación (main.py).


@dataclass(frozen=True)
class AppConfig:
    obs: OBSConfig
    vdoninja: VDONinjaConfig
    youtube: YouTubeConfig
    headless: bool
    log_level: str


def load_config() -> AppConfig:
    obs = OBSConfig(
        host=os.getenv("OBS_HOST", "localhost"),
        port=int(os.getenv("OBS_PORT", "4455")),
        # Contraseña opcional: si el WebSocket de OBS no tiene autenticación
        # habilitada, deja OBS_PASSWORD vacío en el .env.
        password=os.getenv("OBS_PASSWORD", ""),
        executable_path=Path(_require("OBS_EXECUTABLE_PATH")),
        scene_name=_require("OBS_SCENE_NAME"),
        browser_source_name=_require("OBS_BROWSER_SOURCE_NAME"),
        recording_format=os.getenv("OBS_RECORDING_FORMAT", "mkv"),
        startup_wait_seconds=int(os.getenv("OBS_STARTUP_WAIT_SECONDS", "8")),
    )

    vdoninja = VDONinjaConfig(
        url=os.getenv("VDONINJA_URL", "https://vdo.ninja/"),
        invite_button_text=os.getenv(
            "VDONINJA_INVITE_BUTTON_TEXT", "Create Reusable Invite"
        ),
    )

    youtube = YouTubeConfig(
        client_secrets_path=Path(_require("YOUTUBE_CLIENT_SECRETS_PATH")),
        token_path=Path(os.getenv("YOUTUBE_TOKEN_PATH", "youtube_token.json")),
        stream_active_timeout_seconds=int(
            os.getenv("YOUTUBE_STREAM_ACTIVE_TIMEOUT_SECONDS", "60")
        ),
    )

    return AppConfig(
        obs=obs,
        vdoninja=vdoninja,
        youtube=youtube,
        headless=os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
