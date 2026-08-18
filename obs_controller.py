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
        # IMPORTANTE: se fija 'cwd' (directorio de trabajo) a la carpeta del
        # propio ejecutable. OBS necesita esto para localizar sus archivos
        # internos/plugins; sin esto, el proceso puede fallar al iniciar
        # de forma silenciosa (sin ventana visible ni error explícito).
        process = subprocess.Popen(
            [str(self._config.executable_path)],
            cwd=str(self._config.executable_path.parent),
        )

        # Verificación temprana: si el proceso termina casi de inmediato,
        # es señal clara de que algo impidió que OBS abriera (permisos,
        # dependencia faltante, etc.), en vez de simplemente estar cargando.
        time.sleep(2)
        early_exit_code = process.poll()
        if early_exit_code is not None:
            raise OBSControllerError(
                f"OBS se cerró inmediatamente después de intentar abrirlo "
                f"(código de salida: {early_exit_code}). Intenta abrir OBS "
                "manualmente haciendo doble clic en su ícono para ver si "
                "muestra algún error, y verifica que OBS_EXECUTABLE_PATH "
                "apunte exactamente al archivo obs64.exe correcto."
            )

        for attempt in range(1, self._config.startup_wait_seconds + 1):
            time.sleep(1)
            if self._try_connect():
                self._logger.info("Conectado al WebSocket de OBS (intento %s).", attempt)
                return

        raise OBSControllerError(
            "OBS se lanzó pero no fue posible conectar al servidor WebSocket a tiempo. "
            "Verifica que el WebSocket esté habilitado (Herramientas > WebSocket Server Settings) "
            "y considera aumentar OBS_STARTUP_WAIT_SECONDS en tu .env."
        )

    def _try_connect(self) -> bool:
        # Si OBS_PASSWORD está vacío (auth deshabilitada en OBS), obsws-python
        # simplemente ignora este parámetro al conectar.
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
        (por defecto 'mkv'); si no lo es, lo corrige.

        IMPORTANTE: OBS guarda 'RecFormat2' en varias secciones del perfil
        ([AdvOut], [SimpleOutput], [Output]), pero solo la de [AdvOut]
        controla la interfaz cuando el modo de salida es "Avanzado"
        (Settings > Output > Mode = Advanced), que es la configuración
        recomendada para este proyecto. Por eso se usa 'AdvOut' como
        categoría principal.
        """
        client = self._client_or_raise()
        expected = self._config.recording_format.lower()

        # (categoría, nombre_parámetro) en orden de prioridad.
        candidates = [
            ("AdvOut", "RecFormat2"),   # OBS reciente, modo Avanzado (caso esperado)
            ("AdvOut", "RecFormat"),    # OBS más antiguo, modo Avanzado
            ("Output", "RecFormat2"),   # Respaldo genérico
        ]

        current_format = None
        working_candidate = None
        last_error: Exception | None = None

        for category, name in candidates:
            try:
                response = client.get_profile_parameter(category=category, name=name)
            except Exception as exc:
                last_error = exc
                continue

            # El nombre exacto del atributo de respuesta puede variar entre
            # versiones de obsws-python; probamos las variantes conocidas.
            value = (
                getattr(response, "parameter_value", None)
                or getattr(response, "parameterValue", None)
                or (response.get("parameterValue") if isinstance(response, dict) else None)
            )
            if value is not None:
                current_format = value
                working_candidate = (category, name)
                break

        if working_candidate is None:
            raise OBSControllerError(
                "No se pudo leer el formato de grabación actual de OBS en ninguna "
                f"de las categorías conocidas. Último error: {last_error}"
            )

        category, name = working_candidate
        self._logger.info(
            "Formato de grabación leído desde [%s] %s = '%s'.", category, name, current_format
        )

        if current_format.lower() == expected:
            self._logger.info("Formato de grabación ya está en '%s'. OK.", expected)
            return

        self._logger.warning(
            "Formato de grabación actual ('%s') distinto al esperado ('%s'). Corrigiendo en [%s]...",
            current_format,
            expected,
            category,
        )
        try:
            client.set_profile_parameter(category=category, name=name, value=expected)
        except Exception as exc:
            raise OBSControllerError(
                f"No se pudo ajustar el formato de grabación a '{expected}' "
                f"en [{category}] {name}."
            ) from exc

    def set_stream_destination(self, server: str, stream_key: str) -> None:
        """Configura OBS para transmitir a un servidor RTMP personalizado
        (usado para cargar el servidor + stream key que YouTube genera en
        cada transmisión, ya que cambia cada vez).

        NOTA: se llama de forma posicional (no con keywords) porque, según
        vimos con otros métodos de obsws-python, los nombres exactos de los
        parámetros pueden no coincidir con los del protocolo OBS websocket.
        Si esta llamada falla con un error de argumento inesperado, ejecuta
        debug_obs_signature.py adaptado a 'set_stream_service_settings' para
        confirmar la firma real en tu versión instalada.
        """
        client = self._client_or_raise()
        self._logger.info("Configurando destino de streaming en OBS (YouTube)...")
        try:
            client.set_stream_service_settings(
                "rtmp_custom",
                {"server": server, "key": stream_key},
            )
        except Exception as exc:
            raise OBSControllerError(
                "No se pudo configurar el destino de streaming en OBS con el "
                "servidor/stream key de YouTube."
            ) from exc

    def stop_streaming(self) -> None:
        client = self._client_or_raise()
        status = client.get_stream_status()
        if not getattr(status, "output_active", False):
            self._logger.info("OBS ya no estaba transmitiendo. Nada que detener.")
            return

        self._logger.info("Deteniendo transmisión en OBS...")
        try:
            client.stop_stream()
        except Exception as exc:
            raise OBSControllerError("No se pudo detener la transmisión en OBS.") from exc

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
