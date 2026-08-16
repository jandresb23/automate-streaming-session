"""
Ejecuta este script UNA SOLA VEZ (o cada vez que la sesión expire) para
iniciar sesión manualmente en Facebook dentro de un navegador controlado
por Playwright. Al cerrar la ventana, la sesión (cookies) queda guardada
en el archivo indicado por FACEBOOK_STORAGE_STATE, y el flujo automático
principal (main.py) la reutilizará sin pedir login de nuevo.

Uso:
    python setup_facebook_login.py
"""

from playwright.sync_api import sync_playwright

from config import load_config
from logger import setup_logger


def main() -> None:
    config = load_config()
    logger = setup_logger(config.log_level)

    with sync_playwright() as p:
        # Se usa el canal 'chrome' (tu Google Chrome real instalado) en vez del
        # Chromium genérico de Playwright, y se desactivan las señales más
        # comunes que Facebook usa para detectar navegadores automatizados.
        # Requiere haber ejecutado antes: playwright install chrome
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/login")

        logger.info(
            "Inicia sesión manualmente en la ventana de Facebook que se abrió. "
            "Cuando hayas terminado y veas tu inicio (feed), vuelve aquí y presiona ENTER."
        )
        input("Presiona ENTER cuando el login haya terminado... ")

        config.facebook.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(config.facebook.storage_state_path))
        logger.info(
            "Sesión guardada en '%s'. Ya puedes ejecutar main.py.",
            config.facebook.storage_state_path,
        )

        browser.close()


if __name__ == "__main__":
    main()
