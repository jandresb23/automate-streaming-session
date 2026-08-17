"""
YouTubeAutomation: Facade sobre la YouTube Data API v3 (Live Streaming) para
crear la transmisión, obtener el servidor/stream key que se carga en OBS, y
finalmente pasar el broadcast a estado "live" una vez OBS ya está enviando
señal.

A diferencia de Facebook, esto NO usa un navegador ni Playwright: son
llamadas HTTP directas a la API oficial de Google, autenticadas con OAuth2.
Esto evita por completo los problemas de detección de automatización.
"""

from __future__ import annotations

import datetime
import logging
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import YouTubeConfig

SCOPES = ["https://www.googleapis.com/auth/youtube"]


class YouTubeAutomationError(Exception):
    pass


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class YouTubeAutomation:
    def __init__(self, config: YouTubeConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger
        self._youtube = None

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------
    def _load_credentials(self) -> Credentials:
        token_path = self._config.token_path
        creds: Credentials | None = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            self._logger.info("Renovando token de YouTube expirado...")
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
            return creds

        raise YouTubeAutomationError(
            "No hay una sesión válida de YouTube. Ejecuta primero: "
            "python setup_youtube_auth.py"
        )

    def connect(self) -> None:
        self._logger.info("Autenticando con la API de YouTube...")
        creds = self._load_credentials()
        self._youtube = build("youtube", "v3", credentials=creds)

    def _client(self):
        if self._youtube is None:
            raise YouTubeAutomationError("Llama a connect() antes de usar YouTubeAutomation.")
        return self._youtube

    # ------------------------------------------------------------------
    # Operaciones del flujo
    # ------------------------------------------------------------------
    def create_broadcast_and_stream(self, title: str, privacy_status: str) -> tuple[str, str, str, str]:
        """Crea el broadcast y el stream de ingesta, los vincula, y devuelve
        (broadcast_id, stream_id, rtmp_server, stream_key).

        `privacy_status` debe ser 'public' o 'private' (seleccionado por el
        usuario en cada sesión desde la interfaz)."""
        youtube = self._client()

        self._logger.info(
            "Creando transmisión (broadcast) en YouTube: '%s' (visibilidad: %s)",
            title, privacy_status,
        )
        broadcast = (
            youtube.liveBroadcasts()
            .insert(
                part="snippet,status,contentDetails",
                body={
                    "snippet": {
                        "title": title,
                        "scheduledStartTime": _now_iso(),
                    },
                    "status": {
                        "privacyStatus": privacy_status,
                        "selfDeclaredMadeForKids": False,
                    },
                    "contentDetails": {
                        "enableAutoStart": False,
                        "enableAutoStop": False,
                        # Deshabilitado explícitamente: si se deja en su valor
                        # por defecto (habilitado), YouTube exige pasar primero
                        # por el estado intermedio "testing" antes de "live",
                        # y la transición directa ready→live falla con
                        # "invalidTransition".
                        "monitorStream": {"enableMonitorStream": False},
                    },
                },
            )
            .execute()
        )
        broadcast_id = broadcast["id"]

        self._logger.info("Creando stream de ingesta en YouTube...")
        stream = (
            youtube.liveStreams()
            .insert(
                part="snippet,cdn",
                body={
                    "snippet": {"title": f"{title} - stream"},
                    "cdn": {
                        "frameRate": "variable",
                        "ingestionType": "rtmp",
                        "resolution": "variable",
                    },
                },
            )
            .execute()
        )
        stream_id = stream["id"]
        ingestion = stream["cdn"]["ingestionInfo"]
        rtmp_server = ingestion["ingestionAddress"]
        stream_key = ingestion["streamName"]

        self._logger.info("Vinculando broadcast con el stream de ingesta...")
        youtube.liveBroadcasts().bind(
            id=broadcast_id, part="id,contentDetails", streamId=stream_id
        ).execute()

        return broadcast_id, stream_id, rtmp_server, stream_key

    def wait_for_active_stream(self, stream_id: str) -> None:
        """Espera hasta que YouTube detecte la señal RTMP entrante desde OBS
        (streamStatus == 'active') antes de intentar pasar a 'live'."""
        youtube = self._client()
        timeout = self._config.stream_active_timeout_seconds
        poll_interval = 3
        elapsed = 0

        self._logger.info("Esperando a que YouTube detecte la señal de OBS...")
        while elapsed < timeout:
            response = (
                youtube.liveStreams().list(part="status", id=stream_id).execute()
            )
            items = response.get("items", [])
            if items:
                status = items[0]["status"]["streamStatus"]
                if status == "active":
                    self._logger.info("Señal detectada por YouTube (streamStatus=active).")
                    return
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise YouTubeAutomationError(
            f"YouTube no detectó señal activa del stream en {timeout} segundos. "
            "Verifica que OBS esté transmitiendo correctamente hacia el servidor/stream key configurado."
        )

    def go_live(self, broadcast_id: str) -> None:
        youtube = self._client()
        self._logger.info("Transicionando el broadcast a estado 'live'...")
        try:
            youtube.liveBroadcasts().transition(
                broadcastStatus="live", id=broadcast_id, part="id,status"
            ).execute()
        except Exception as exc:
            raise YouTubeAutomationError(
                f"No se pudo transicionar el broadcast a 'live': {exc}"
            ) from exc
