"""
VDONinjaAutomation: abre VDO.Ninja, hace clic en "Create Reusable Invite"
(que abre un panel de configuración), luego en "GENERATE THE INVITE LINK"
dentro de ese panel, y extrae del DOM la URL que debe cargarse en OBS
(Browser Source).

NOTA IMPORTANTE SOBRE SELECTORES:
La interfaz de VDO.Ninja puede cambiar con el tiempo. Los selectores usados
aquí se basan en el TEXTO VISIBLE de los elementos (más resistente a cambios
que un selector CSS/XPath fijo), pero si VDO.Ninja actualiza su interfaz,
puede ser necesario ajustar `_extract_viewer_url`.

Para depurar/ajustar selectores rápidamente se recomienda usar:
    playwright codegen https://vdo.ninja/
"""

from __future__ import annotations

import logging
import re

from playwright.sync_api import Page

from config import VDONinjaConfig


class VDONinjaAutomationError(Exception):
    pass


class VDONinjaAutomation:
    GENERATE_BUTTON_TEXT = "GENERATE THE INVITE LINK"

    def __init__(self, page: Page, config: VDONinjaConfig, logger: logging.Logger):
        self._page = page
        self._config = config
        self._logger = logger

    def open(self) -> None:
        self._logger.info("Abriendo VDO.Ninja...")
        self._page.goto(self._config.url, wait_until="domcontentloaded")

    def create_reusable_invite(self) -> str:
        """Abre el panel de invitación reutilizable, genera el link, y
        devuelve la URL del visor (la que se debe usar en el Browser
        Source de OBS)."""
        self._logger.info(
            "Buscando botón '%s' en VDO.Ninja...", self._config.invite_button_text
        )
        open_panel_button = self._page.get_by_text(
            self._config.invite_button_text, exact=False
        ).first
        try:
            open_panel_button.click(timeout=10_000)
        except Exception as exc:
            raise VDONinjaAutomationError(
                f"No se encontró o no se pudo hacer clic en el botón "
                f"'{self._config.invite_button_text}'. Verifica el texto exacto "
                "en VDONINJA_INVITE_BUTTON_TEXT (.env) o el estado actual del sitio."
            ) from exc

        self._page.wait_for_timeout(500)  # deja tiempo a que el panel se abra

        self._logger.info("Haciendo clic en '%s'...", self.GENERATE_BUTTON_TEXT)
        generate_button = self._page.get_by_text(self.GENERATE_BUTTON_TEXT, exact=False).first
        try:
            generate_button.click(timeout=10_000)
        except Exception as exc:
            raise VDONinjaAutomationError(
                f"No se encontró o no se pudo hacer clic en '{self.GENERATE_BUTTON_TEXT}' "
                "dentro del panel de invitación reutilizable. Puede que el texto haya "
                "cambiado; revisa con 'playwright codegen https://vdo.ninja/'."
            ) from exc

        self._page.wait_for_timeout(1500)  # deja tiempo a que el QR/URL se rendericen
        return self._extract_viewer_url()

    def _extract_viewer_url(self) -> str:
        """Recorre los campos de texto e inputs visibles en pantalla buscando
        una URL de vdo.ninja que corresponda al modo 'view' (visor)."""
        candidates: list[str] = []

        # Los inputs de solo lectura son el patrón más común en VDO.Ninja
        # para mostrar enlaces generados.
        inputs = self._page.locator("input[type='text'], input:not([type])")
        count = inputs.count()
        for i in range(count):
            try:
                value = inputs.nth(i).input_value(timeout=1000)
            except Exception:
                continue
            if value and "vdo.ninja" in value:
                candidates.append(value)

        # Respaldo: buscar el patrón directamente en el texto visible de la página.
        if not candidates:
            content = self._page.content()
            found = re.findall(r"https?://vdo\.ninja/\?[^\s\"'<]+", content)
            candidates.extend(found)

        viewer_urls = [u for u in candidates if "view=" in u or "&view" in u]
        chosen = viewer_urls[0] if viewer_urls else (candidates[0] if candidates else None)

        if not chosen:
            raise VDONinjaAutomationError(
                "No se pudo extraer ninguna URL de vdo.ninja de la página tras generar "
                "la invitación. Puede que el marcado haya cambiado; revisa manualmente "
                "con 'playwright codegen https://vdo.ninja/'."
            )

        self._logger.info("URL de visor obtenida correctamente.")
        return chosen

    def _extract_viewer_url(self) -> str:
        """Recorre los campos de texto e inputs visibles en pantalla buscando
        una URL de vdo.ninja que corresponda al modo 'view' (visor)."""
        candidates: list[str] = []

        # Los inputs de solo lectura son el patrón más común en VDO.Ninja
        # para mostrar enlaces generados.
        inputs = self._page.locator("input[type='text'], input:not([type])")
        count = inputs.count()
        for i in range(count):
            try:
                value = inputs.nth(i).input_value(timeout=1000)
            except Exception:
                continue
            if value and "vdo.ninja" in value:
                candidates.append(value)

        # Respaldo: buscar el patrón directamente en el texto visible de la página.
        if not candidates:
            content = self._page.content()
            found = re.findall(r"https?://vdo\.ninja/\?[^\s\"'<]+", content)
            candidates.extend(found)

        viewer_urls = [u for u in candidates if "view=" in u or "&view" in u]
        chosen = viewer_urls[0] if viewer_urls else (candidates[0] if candidates else None)

        if not chosen:
            raise VDONinjaAutomationError(
                "No se pudo extraer ninguna URL de vdo.ninja de la página tras crear "
                "la invitación. Puede que el marcado haya cambiado; revisa manualmente "
                "con 'playwright codegen https://vdo.ninja/'."
            )

        self._logger.info("URL de visor obtenida correctamente.")
        return chosen
