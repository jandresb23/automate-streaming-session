"""
OBSController: Facade que expone solo las operaciones que necesita este
proyecto (actualizar URL del Browser Source, validar formato de grabación,
iniciar streaming), ocultando los detalles del protocolo WebSocket.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

import obsws_python as obs

from config import OBSConfig


class OBSControllerError(Exception):
    """Error específico de la integración con OBS."""


class OBSController:
    def __init__(self, config: OBSConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger
        self._client: obs.ReqClient | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def ensure_running(self) -> None:
        """Verifica si OBS está abierto (probando la conexión WebSocket);
        si no, lo lanza como proceso y espera a que esté disponible."""
        if self._try_connect():
            self._logger.info("OBS ya estaba en ejecución.")
            return

        if not self._config.executable_path.exists():
            raise OBSControllerError(
                f"No se encontró el ejecutable de OBS en: {self._config.executable_path}. "
                "Verifica OBS_EXECUTABLE_PATH en tu .env."
            )

        self._logger.info("OBS no estaba abierto. Iniciando proceso...")
        subprocess.Popen([str(self._config.executable_path)])

        for attempt in range(1, self._config.startup_wait_seconds + 1):
            time.sleep(1)
            if self._try_connect():
                self._logger.info("Conectado al WebSocket de OBS (intento %s).", attempt)
                return

        raise OBSControllerError(
            "OBS se lanzó pero no fue posible conectar al servidor WebSocket a tiempo. "
            "Verifica que el WebSocket esté habilitado (Herramientas > WebSocket Server Settings)."
        )

    def _try_connect(self) -> bool:
        try:
            self._client = obs.ReqClient(
                host=self._config.host,
                port=self._config.port,
                password=self._config.password,
                timeout=3,
            )
            self._client.get_version()
            return True
        except Exception:
            self._client = None
            return False

    def disconnect(self) -> None:
        # obsws-python cierra la conexión al perder la referencia; no requiere
        # un cierre explícito, pero dejamos el hook por claridad y futuras versiones.
        self._client = None

    def _client_or_raise(self) -> obs.ReqClient:
        if self._client is None:
            raise OBSControllerError("No hay conexión activa con OBS. Llama a ensure_running() primero.")
        return self._client

    # ------------------------------------------------------------------
    # Operaciones del flujo
    # ------------------------------------------------------------------
    def update_browser_source_url(self, url: str) -> None:
        client = self._client_or_raise()
        source_name = self._config.browser_source_name
        self._logger.info("Actualizando Browser Source '%s' con la nueva URL de VDO.Ninja.", source_name)
        try:
            client.set_input_settings(
                name=source_name,
                settings={"url": url},
                overlay=True,
            )
        except Exception as exc:
            raise OBSControllerError(
                f"No se pudo actualizar el Browser Source '{source_name}'. "
                f"Verifica que exista con ese nombre exacto en la escena '{self._config.scene_name}'."
            ) from exc

    def validate_recording_format(self) -> None:
        """Valida que el formato de grabación configurado sea el esperado
        (por defecto 'mkv'); si no lo es, lo corrige."""
        client = self._client_or_raise()
        expected = self._config.recording_format.lower()

        try:
            current = client.get_profile_parameter(
                parameter_category="Output", parameter_name="RecFormat2"
            )
            current_format = getattr(current, "parameter_value", None)
        except Exception as exc:
            raise OBSControllerError(
                "No se pudo leer el formato de grabación actual de OBS."
            ) from exc

        if current_format and current_format.lower() == expected:
            self._logger.info("Formato de grabación ya está en '%s'. OK.", expected)
            return

        self._logger.warning(
            "Formato de grabación actual ('%s') distinto al esperado ('%s'). Corrigiendo...",
            current_format,
            expected,
        )
        try:
            client.set_profile_parameter(
                parameter_category="Output",
                parameter_name="RecFormat2",
                parameter_value=expected,
            )
        except Exception as exc:
            raise OBSControllerError(
                "No se pudo ajustar el formato de grabación a Matroska (mkv). "
                "Puede que tu versión de OBS use un nombre de parámetro distinto "
                "('RecFormat' en vez de 'RecFormat2'); revisa la documentación de obs-websocket "
                "para tu versión instalada."
            ) from exc

    def start_streaming(self) -> None:
        client = self._client_or_raise()
        status = client.get_stream_status()
        if getattr(status, "output_active", False):
            self._logger.info("OBS ya estaba transmitiendo. No se reinicia el stream.")
            return

        self._logger.info("Iniciando transmisión en OBS...")
        try:
            client.start_stream()
        except Exception as exc:
            raise OBSControllerError("No se pudo iniciar la transmisión en OBS.") from exc
