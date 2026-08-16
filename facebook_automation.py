"""
FacebookAutomation: inserta el título de la transmisión y hace clic en
"Iniciar transmisión en vivo" usando el perfil personal, reutilizando una
sesión ya autenticada (storage_state) para no repetir el login cada vez.

SEGURIDAD:
El archivo de sesión (FACEBOOK_STORAGE_STATE) contiene cookies válidas de
tu cuenta. Debe tratarse como una credencial:
  - Está excluido de git (.gitignore).
  - No debe compartirse ni subirse a ningún repositorio o almacenamiento
    compartido sin cifrar.

NOTA SOBRE SELECTORES:
La interfaz de Facebook Live Producer cambia con frecuencia y varía según
idioma/región/experimento A-B de Meta. Los selectores aquí son un punto de
partida basado en roles y texto; verifica y ajusta con:
    playwright codegen https://www.facebook.com/live/producer
"""

from __future__ import annotations

import logging

from playwright.sync_api import Page

from config import FacebookConfig


class FacebookAutomationError(Exception):
    pass


class FacebookAutomation:
    def __init__(self, page: Page, config: FacebookConfig, logger: logging.Logger):
        self._page = page
        self._config = config
        self._logger = logger

    def open_live_producer(self) -> None:
        self._logger.info("Abriendo Facebook Live Producer...")
        self._page.goto(self._config.live_producer_url, wait_until="domcontentloaded")
        self._page.wait_for_timeout(2000)

        if "login" in self._page.url:
            raise FacebookAutomationError(
                "Facebook redirigió a la pantalla de login. La sesión guardada "
                "(FACEBOOK_STORAGE_STATE) expiró o no es válida. "
                "Vuelve a ejecutar setup_facebook_login.py para regenerarla."
            )

    def set_title(self, title: str) -> None:
        self._logger.info("Insertando título de la transmisión...")
        title_field = self._page.get_by_placeholder("Title", exact=False).or_(
            self._page.get_by_label("Title", exact=False)
        )
        try:
            title_field.first.fill(title, timeout=10_000)
        except Exception as exc:
            raise FacebookAutomationError(
                "No se pudo encontrar o completar el campo de título en Facebook Live "
                "Producer. Ajusta el selector en facebook_automation.py (set_title)."
            ) from exc

    def start_live(self) -> None:
        self._logger.info("Haciendo clic en 'Iniciar transmisión en vivo'...")
        start_button = self._page.get_by_role("button", name="Go Live", exact=False).or_(
            self._page.get_by_role("button", name="Iniciar transmisión en vivo", exact=False)
        )
        try:
            start_button.first.click(timeout=10_000)
        except Exception as exc:
            raise FacebookAutomationError(
                "No se pudo hacer clic en el botón de inicio de transmisión de Facebook. "
                "Ajusta el selector en facebook_automation.py (start_live)."
            ) from exc
