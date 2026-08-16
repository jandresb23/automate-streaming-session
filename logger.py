"""
Configuración de logging para todo el proyecto.

Regla de seguridad: nunca se debe registrar la contraseña de OBS ni el
contenido de la sesión de Facebook. Los métodos que manejan esos datos
loguean solo mensajes descriptivos (ej. "conectado a OBS"), nunca el valor.
"""

import logging
import sys


def setup_logger(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("stream_automation")
    logger.setLevel(level.upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
