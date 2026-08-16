"""
Script de prueba aislado para verificar la integración con OBS Studio,
SIN tocar VDO.Ninja ni Facebook. Útil para validar la configuración del
.env y el comportamiento de obs_controller.py antes de correr el flujo
completo.

Requisitos antes de ejecutar:
  - El archivo .env ya debe estar completo (ver .env.example).
  - En OBS ya debe existir la escena (OBS_SCENE_NAME) y el Browser Source
    (OBS_BROWSER_SOURCE_NAME) configurados manualmente al menos una vez.

Uso:
    python test_obs.py
"""

from config import load_config
from logger import setup_logger
from obs_controller import OBSController, OBSControllerError


def ask_yes_no(question: str) -> bool:
    answer = input(f"{question} (s/n): ").strip().lower()
    return answer in ("s", "si", "sí", "y", "yes")


def main() -> None:
    config = load_config()
    logger = setup_logger(config.log_level)
    obs = OBSController(config.obs, logger)

    print("\n=== PRUEBA AISLADA DE OBS ===\n")

    # 1. Verificar / iniciar OBS y conectar por WebSocket
    try:
        obs.ensure_running()
        print("✅ Conexión con OBS establecida correctamente.\n")
    except OBSControllerError as exc:
        print(f"❌ No se pudo conectar con OBS: {exc}")
        return

    # 2. Actualizar el Browser Source con una URL de prueba
    if ask_yes_no(
        f"¿Actualizar el Browser Source '{config.obs.browser_source_name}' "
        "con una URL de prueba (https://vdo.ninja/?room=test)?"
    ):
        try:
            obs.update_browser_source_url("https://vdo.ninja/?room=test")
            print("✅ Browser Source actualizado correctamente.\n")
        except OBSControllerError as exc:
            print(f"❌ Falló al actualizar el Browser Source: {exc}\n")

    # 3. Validar/corregir formato de grabación (Matroska)
    if ask_yes_no("¿Validar y, si hace falta, corregir el formato de grabación a Matroska (mkv)?"):
        try:
            obs.validate_recording_format()
            print("✅ Formato de grabación validado/corregido correctamente.\n")
        except OBSControllerError as exc:
            print(f"❌ Falló al validar el formato de grabación: {exc}\n")

    # 4. Iniciar streaming (ADVERTENCIA: esto sí pone a OBS a transmitir de verdad
    #    hacia el destino que tengas configurado, ej. Facebook)
    print("⚠️  El siguiente paso INICIA LA TRANSMISIÓN REAL en OBS hacia el destino configurado.")
    if ask_yes_no("¿Deseas iniciar la transmisión ahora?"):
        try:
            obs.start_streaming()
            print("✅ Transmisión iniciada en OBS. Recuerda detenerla manualmente cuando termines.\n")
        except OBSControllerError as exc:
            print(f"❌ Falló al iniciar la transmisión: {exc}\n")
    else:
        print("Transmisión NO iniciada (paso omitido por el usuario).\n")

    obs.disconnect()
    print("=== FIN DE LA PRUEBA ===")


if __name__ == "__main__":
    main()
