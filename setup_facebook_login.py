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
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
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
