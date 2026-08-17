"""
Ejecuta este script UNA SOLA VEZ (o cuando el token expire sin poder
renovarse automáticamente) para autorizar la aplicación contra tu cuenta
de YouTube vía OAuth2.

Requisitos previos:
  1. En Google Cloud Console, tener un proyecto con la "YouTube Data API v3"
     habilitada.
  2. Haber creado una credencial OAuth de tipo "Aplicación de escritorio"
     (Desktop app) y descargado el archivo JSON correspondiente.
  3. Colocar la ruta a ese archivo en YOUTUBE_CLIENT_SECRETS_PATH (.env).

Al ejecutar este script se abrirá tu navegador pidiéndote iniciar sesión
con tu cuenta de Google y autorizar el acceso. El token resultante se
guarda en YOUTUBE_TOKEN_PATH (.env) para reutilizarse automáticamente en
cada ejecución de main.py.

Uso:
    python setup_youtube_auth.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow

from config import load_config
from logger import setup_logger
from youtube_automation import SCOPES


def main() -> None:
    config = load_config()
    logger = setup_logger(config.log_level)

    client_secrets_path = config.youtube.client_secrets_path
    if not client_secrets_path.exists():
        raise SystemExit(
            f"No se encontró el archivo de credenciales OAuth en: {client_secrets_path}. "
            "Descárgalo desde Google Cloud Console (Credenciales > ID de cliente OAuth > "
            "Aplicación de escritorio) y verifica YOUTUBE_CLIENT_SECRETS_PATH en tu .env."
        )

    logger.info("Iniciando flujo de autorización OAuth con YouTube...")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    credentials = flow.run_local_server(port=0)

    token_path = config.youtube.token_path
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json())

    logger.info("Autorización completada. Token guardado en '%s'.", token_path)
    logger.info("Ya puedes ejecutar main.py.")


if __name__ == "__main__":
    main()
