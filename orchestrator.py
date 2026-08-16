"""
Orchestrator: coordina la secuencia completa de alistamiento del streaming.

Orden (según lo definido con el usuario):
  1. Iniciar Facebook
  2. Insertar título de sesión
  3. Abrir VDO.Ninja
  4. Clic en "Create Reusable Invite" (genera QR + URL)
  5. Almacenar la URL
  6. (Manual) El usuario escanea el QR con su móvil
  7. Iniciar OBS Studio
  8. Insertar la URL en el Browser Source
  9. Validar formato de video (Matroska)
  10. Iniciar transmisión en OBS
  11. Ir a Facebook y hacer clic en iniciar transmisión
"""

from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright

from config import AppConfig
from facebook_automation import FacebookAutomation, FacebookAutomationError
from obs_controller import OBSController, OBSControllerError
from vdoninja_automation import VDONinjaAutomation, VDONinjaAutomationError


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

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._config.headless)

            # --- Contexto de Facebook (sesión persistente) ---
            fb_state_path = self._config.facebook.storage_state_path
            if not fb_state_path.exists():
                raise OrchestratorError(
                    f"No existe el archivo de sesión de Facebook ('{fb_state_path}'). "
                    "Ejecuta primero: python setup_facebook_login.py"
                )
            fb_context = browser.new_context(storage_state=str(fb_state_path))
            fb_page = fb_context.new_page()
            facebook = FacebookAutomation(fb_page, self._config.facebook, self._logger)

            # --- Contexto de VDO.Ninja (sin sesión, no la necesita) ---
            vdo_context = browser.new_context()
            vdo_page = vdo_context.new_page()
            vdoninja = VDONinjaAutomation(vdo_page, self._config.vdoninja, self._logger)

            try:
                # 1-2: Facebook, título
                self._step("1-2. Facebook: abrir y colocar título", facebook.open_live_producer)
                self._step(
                    "1-2. Facebook: insertar título",
                    lambda: facebook.set_title(title),
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

                # 10: iniciar transmisión en OBS
                self._step("10. OBS: iniciar transmisión", obs_controller.start_streaming)

                # 11: Facebook, iniciar transmisión
                self._step("11. Facebook: iniciar transmisión en vivo", facebook.start_live)

                self._logger.info("✅ Alistamiento completado. La transmisión está en vivo.")

            except (OBSControllerError, VDONinjaAutomationError, FacebookAutomationError) as exc:
                raise OrchestratorError(str(exc)) from exc
            finally:
                fb_context.close()
                vdo_context.close()
                browser.close()
                obs_controller.disconnect()

    def _step(self, description: str, action):
        self._logger.info("▶ %s", description)
        try:
            return action()
        except Exception:
            self._logger.error("✖ Falló en: %s", description)
            raise
