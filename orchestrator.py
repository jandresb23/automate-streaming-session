"""
Orchestrator: coordina la secuencia completa de alistamiento del streaming.

Orden actualizado (YouTube reemplaza a Facebook como servidor de transmisión):
  1. Crear transmisión (broadcast) en YouTube con el título de la sesión
  2. Crear el stream de ingesta y vincularlo al broadcast (API de YouTube)
  3. Abrir VDO.Ninja
  4. Clic en "Create Reusable Invite" (genera QR + URL)
  5. Almacenar la URL
  6. (Manual) El usuario escanea el QR con su móvil
  7. Iniciar OBS Studio
  8. Insertar la URL de VDO.Ninja en el Browser Source
  9. Validar formato de video (Matroska)
  10. Configurar en OBS el servidor/stream key de YouTube e iniciar transmisión
  11. Esperar a que YouTube detecte la señal y transicionar el broadcast a "live"

A diferencia del flujo con Facebook, aquí NO se usa Playwright/navegador para
YouTube — solo llamadas directas a su API oficial, mucho más robustas.
"""

from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright

from config import AppConfig
from obs_controller import OBSController, OBSControllerError
from vdoninja_automation import VDONinjaAutomation, VDONinjaAutomationError
from youtube_automation import YouTubeAutomation, YouTubeAutomationError


class OrchestratorError(Exception):
    """Error irrecuperable durante el flujo de alistamiento."""


class Orchestrator:
    def __init__(self, config: AppConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger

    def run(self, title: str, wait_for_qr_scan) -> None:
        """
        Ejecuta el flujo completo.

        `title` es el título de la sesión, solicitado por la interfaz antes
        de iniciar el proceso (varía en cada transmisión).

        `wait_for_qr_scan` es una función sin argumentos que se invoca en el
        paso 6 (manual) para pausar hasta que el usuario confirme que ya
        escaneó el QR con el móvil. Se inyecta así para que la interfaz
        (tkinter, consola, etc.) decida cómo pedir esa confirmación.
        """
        if not title or not title.strip():
            raise OrchestratorError("El título de la sesión no puede estar vacío.")

        obs_controller = OBSController(self._config.obs, self._logger)
        youtube = YouTubeAutomation(self._config.youtube, self._logger)

        with sync_playwright() as playwright:
            # Solo VDO.Ninja necesita navegador; YouTube usa su API directamente.
            vdo_browser = playwright.chromium.launch(
                channel="chrome", headless=self._config.headless
            )
            vdo_context = vdo_browser.new_context()
            vdo_page = vdo_context.new_page()
            vdoninja = VDONinjaAutomation(vdo_page, self._config.vdoninja, self._logger)

            try:
                # 1-2: YouTube — crear broadcast + stream, vincular
                self._step("1. YouTube: autenticar", youtube.connect)
                broadcast_id, stream_id, rtmp_server, stream_key = self._step(
                    "1-2. YouTube: crear transmisión y stream de ingesta",
                    lambda: youtube.create_broadcast_and_stream(title),
                )

                # 3-5: VDO.Ninja, invitación y URL
                self._step("3. VDO.Ninja: abrir", vdoninja.open)
                viewer_url = self._step(
                    "4-5. VDO.Ninja: crear invitación y obtener URL",
                    vdoninja.create_reusable_invite,
                )
                self._logger.info("URL almacenada para OBS (paso 5 completado).")

                # 6: manual — escaneo de QR
                self._logger.info("Paso 6: esperando confirmación de escaneo del QR por el usuario...")
                wait_for_qr_scan()

                # 7: iniciar OBS
                self._step("7. OBS: verificar/iniciar aplicación", obs_controller.ensure_running)

                # 8: insertar URL en Browser Source
                self._step(
                    "8. OBS: actualizar Browser Source con la URL de VDO.Ninja",
                    lambda: obs_controller.update_browser_source_url(viewer_url),
                )

                # 9: validar formato Matroska
                self._step("9. OBS: validar formato de grabación (mkv)", obs_controller.validate_recording_format)

                # 10: configurar destino YouTube e iniciar transmisión en OBS
                self._step(
                    "10. OBS: configurar servidor/stream key de YouTube",
                    lambda: obs_controller.set_stream_destination(rtmp_server, stream_key),
                )
                self._step("10. OBS: iniciar transmisión", obs_controller.start_streaming)

                # 11: esperar señal activa y pasar el broadcast a "live"
                self._step(
                    "11. YouTube: esperar señal activa",
                    lambda: youtube.wait_for_active_stream(stream_id),
                )
                self._step(
                    "11. YouTube: iniciar transmisión en vivo",
                    lambda: youtube.go_live(broadcast_id),
                )

                self._logger.info("✅ Alistamiento completado. La transmisión está en vivo.")

            except (OBSControllerError, VDONinjaAutomationError, YouTubeAutomationError) as exc:
                raise OrchestratorError(str(exc)) from exc
            finally:
                vdo_context.close()
                vdo_browser.close()
                obs_controller.disconnect()

    def _step(self, description: str, action):
        self._logger.info("▶ %s", description)
        try:
            return action()
        except Exception:
            self._logger.error("✖ Falló en: %s", description)
            raise
