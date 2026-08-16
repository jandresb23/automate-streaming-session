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
class FacebookConfig:
    storage_state_path: Path
    live_producer_url: str
    # El título ya NO se lee de .env: se solicita al usuario en cada sesión
    # desde la interfaz (ver main.py).


@dataclass(frozen=True)
class AppConfig:
    obs: OBSConfig
    vdoninja: VDONinjaConfig
    facebook: FacebookConfig
    headless: bool
    log_level: str


def load_config() -> AppConfig:
    obs = OBSConfig(
        host=os.getenv("OBS_HOST", "localhost"),
        port=int(os.getenv("OBS_PORT", "4455")),
        password=_require("OBS_PASSWORD"),
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

    facebook = FacebookConfig(
        storage_state_path=Path(
            os.getenv("FACEBOOK_STORAGE_STATE", "facebook_session.json")
        ),
        live_producer_url=os.getenv(
            "FACEBOOK_LIVE_PRODUCER_URL", "https://www.facebook.com/live/producer"
        ),
    )

    return AppConfig(
        obs=obs,
        vdoninja=vdoninja,
        facebook=facebook,
        headless=os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
