"""
Punto de entrada de la aplicación: una ventana con un único botón
"Iniciar alistamiento" que ejecuta las 11 etapas definidas en Orchestrator.

El proceso corre en un hilo separado para no congelar la interfaz, y el
paso manual (escaneo de QR) se resuelve con una ventana de confirmación.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

from config import load_config
from logger import setup_logger
from orchestrator import Orchestrator, OrchestratorError


class App:
    def __init__(self) -> None:
        self.config = load_config()
        self.logger = setup_logger(self.config.log_level)
        self.orchestrator = Orchestrator(self.config, self.logger)

        self.root = tk.Tk()
        self.root.title("Alistamiento de Streaming")
        self.root.geometry("380x220")

        self.status_var = tk.StringVar(value="Listo para iniciar.")
        self.title_var = tk.StringVar(value="")

        tk.Label(
            self.root, text="Alistamiento automático de streaming",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(20, 10))

        tk.Label(self.root, text="Título de la sesión:").pack()
        self.title_entry = tk.Entry(self.root, textvariable=self.title_var, width=36)
        self.title_entry.pack(pady=(0, 10))
        self.title_entry.focus()

        self.start_button = tk.Button(
            self.root, text="Iniciar alistamiento",
            font=("Segoe UI", 11), width=24, command=self._on_start_click,
        )
        self.start_button.pack(pady=5)

        tk.Label(self.root, textvariable=self.status_var, fg="gray", wraplength=340).pack(pady=10)

    def _on_start_click(self) -> None:
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Título requerido", "Ingresa el título de la sesión antes de continuar.")
            return

        self.start_button.config(state=tk.DISABLED)
        self.title_entry.config(state=tk.DISABLED)
        self.status_var.set("Ejecutando alistamiento...")
        thread = threading.Thread(target=self._run_flow, args=(title,), daemon=True)
        thread.start()

    def _run_flow(self, title: str) -> None:
        try:
            self.orchestrator.run(title=title, wait_for_qr_scan=self._wait_for_qr_scan_dialog)
            self._set_status_threadsafe("✅ Transmisión iniciada correctamente.")
        except OrchestratorError as exc:
            self.logger.error("Error en el flujo: %s", exc)
            self._set_status_threadsafe(f"❌ Error: {exc}")
        except Exception as exc:  # salvaguarda ante errores no anticipados
            self.logger.exception("Error inesperado durante el alistamiento.")
            self._set_status_threadsafe(f"❌ Error inesperado: {exc}")
        finally:
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.title_entry.config(state=tk.NORMAL))

    def _wait_for_qr_scan_dialog(self) -> None:
        """Se ejecuta en el hilo de trabajo; usa un evento para bloquear
        hasta que el usuario confirme en la interfaz principal."""
        event = threading.Event()

        def show_dialog():
            messagebox.showinfo(
                "Escanear QR",
                "Escanea el código QR de VDO.Ninja con tu móvil.\n\n"
                "Cuando la cámara ya esté transmitiendo, presiona OK para continuar.",
            )
            event.set()

        self.root.after(0, show_dialog)
        event.wait()

    def _set_status_threadsafe(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
