"""
Punto de entrada de la aplicación: una ventana con campo de título,
descripción opcional, selector de visibilidad (público/privado), un botón
"Iniciar alistamiento" y un botón "Detener transmisión" (habilitado solo
mientras hay una sesión activa).

El proceso corre en un hilo separado para no congelar la interfaz, y el
paso manual (escaneo de QR) se resuelve con una ventana de confirmación.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageTk

from config import load_config
from logger import setup_logger
from orchestrator import Orchestrator, OrchestratorError

LOGO_PATH = Path(__file__).parent / "assets" / "cursal_logo.png"
LOGO_MAX_WIDTH = 260  # píxeles


class App:
    def __init__(self) -> None:
        self.config = load_config()
        self.logger = setup_logger(self.config.log_level)
        self.orchestrator = Orchestrator(self.config, self.logger)

        # Guarda el broadcast_id de la sesión activa, necesario para poder
        # detenerla después. None mientras no hay ninguna transmisión en curso.
        self._active_broadcast_id: str | None = None

        self.root = tk.Tk()
        self.root.title("Alistamiento de Streaming")
        self.root.geometry("400x480")

        self.status_var = tk.StringVar(value="Listo para iniciar.")
        self.title_var = tk.StringVar(value="")
        self.privacy_var = tk.StringVar(value="private")

        self._logo_image = self._load_logo()  # se guarda la referencia para que no se pierda
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image).pack(pady=(15, 5))

        tk.Label(
            self.root, text="Alistamiento automático de streaming",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(0, 10))

        tk.Label(self.root, text="Título de la sesión:").pack()
        self.title_entry = tk.Entry(self.root, textvariable=self.title_var, width=40)
        self.title_entry.pack(pady=(0, 10))
        self.title_entry.focus()

        tk.Label(self.root, text="Descripción (opcional):").pack()
        self.description_text = tk.Text(self.root, width=40, height=4, wrap=tk.WORD)
        self.description_text.pack(pady=(0, 10))

        tk.Label(self.root, text="Visibilidad del video:").pack()
        privacy_frame = tk.Frame(self.root)
        privacy_frame.pack(pady=(0, 10))
        self.privacy_public_radio = tk.Radiobutton(
            privacy_frame, text="Público", variable=self.privacy_var, value="public",
        )
        self.privacy_public_radio.pack(side=tk.LEFT, padx=10)
        self.privacy_private_radio = tk.Radiobutton(
            privacy_frame, text="Privado", variable=self.privacy_var, value="private",
        )
        self.privacy_private_radio.pack(side=tk.LEFT, padx=10)

        self.start_button = tk.Button(
            self.root, text="Iniciar alistamiento",
            font=("Segoe UI", 11), width=26, command=self._on_start_click,
        )
        self.start_button.pack(pady=5)

        self.stop_button = tk.Button(
            self.root, text="Detener transmisión",
            font=("Segoe UI", 11), width=26, command=self._on_stop_click,
            state=tk.DISABLED, fg="white", bg="#b3261e",
            activeforeground="white", activebackground="#8f1e18",
        )
        self.stop_button.pack(pady=5)

        tk.Label(self.root, textvariable=self.status_var, fg="gray", wraplength=360).pack(pady=10)

    # ------------------------------------------------------------------
    # Iniciar transmisión
    # ------------------------------------------------------------------
    def _on_start_click(self) -> None:
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Título requerido", "Ingresa el título de la sesión antes de continuar.")
            return
        description = self.description_text.get("1.0", tk.END).strip()
        privacy_status = self.privacy_var.get()

        self._set_inputs_state(tk.DISABLED)
        self.status_var.set("Ejecutando alistamiento...")
        thread = threading.Thread(
            target=self._run_start_flow, args=(title, description, privacy_status), daemon=True
        )
        thread.start()

    def _run_start_flow(self, title: str, description: str, privacy_status: str) -> None:
        try:
            broadcast_id = self.orchestrator.run(
                title=title,
                privacy_status=privacy_status,
                wait_for_qr_scan=self._wait_for_qr_scan_dialog,
                description=description,
            )
            self._active_broadcast_id = broadcast_id
            self._set_status_threadsafe("✅ Transmisión iniciada correctamente.")
            self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))
        except OrchestratorError as exc:
            self.logger.error("Error en el flujo: %s", exc)
            self._set_status_threadsafe(f"❌ Error: {exc}")
            self.root.after(0, lambda: self._set_inputs_state(tk.NORMAL))
        except Exception as exc:  # salvaguarda ante errores no anticipados
            self.logger.exception("Error inesperado durante el alistamiento.")
            self._set_status_threadsafe(f"❌ Error inesperado: {exc}")
            self.root.after(0, lambda: self._set_inputs_state(tk.NORMAL))

    # ------------------------------------------------------------------
    # Detener transmisión
    # ------------------------------------------------------------------
    def _on_stop_click(self) -> None:
        if not self._active_broadcast_id:
            return

        confirmed = messagebox.askyesno(
            "Detener transmisión",
            "Esto finalizará la transmisión en YouTube y detendrá el streaming en OBS. ¿Continuar?",
        )
        if not confirmed:
            return

        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Deteniendo transmisión...")
        thread = threading.Thread(target=self._run_stop_flow, daemon=True)
        thread.start()

    def _run_stop_flow(self) -> None:
        broadcast_id = self._active_broadcast_id
        try:
            self.orchestrator.stop_session(broadcast_id)
            self._active_broadcast_id = None
            self._set_status_threadsafe("⏹ Transmisión detenida. Listo para iniciar una nueva.")
            self.root.after(0, lambda: self._set_inputs_state(tk.NORMAL))
        except OrchestratorError as exc:
            self.logger.error("Error al detener la transmisión: %s", exc)
            self._set_status_threadsafe(f"❌ Error al detener: {exc}")
            # Se reactiva el botón de detener por si se quiere reintentar,
            # ya que la transmisión podría seguir activa del lado de YouTube/OBS.
            self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))
        except Exception as exc:  # salvaguarda ante errores no anticipados
            self.logger.exception("Error inesperado al detener la transmisión.")
            self._set_status_threadsafe(f"❌ Error inesperado al detener: {exc}")
            self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))

    # ------------------------------------------------------------------
    # Utilidades de interfaz
    # ------------------------------------------------------------------
    def _load_logo(self) -> ImageTk.PhotoImage | None:
        """Carga el logo desde assets/, redimensionado manteniendo la
        proporción. Si el archivo no existe, la app sigue funcionando
        normalmente sin logo (no es un error crítico)."""
        if not LOGO_PATH.exists():
            self.logger.warning("No se encontró el logo en '%s'; se omite.", LOGO_PATH)
            return None

        try:
            image = Image.open(LOGO_PATH)
            width, height = image.size
            if width > LOGO_MAX_WIDTH:
                ratio = LOGO_MAX_WIDTH / width
                image = image.resize(
                    (LOGO_MAX_WIDTH, int(height * ratio)), Image.LANCZOS
                )
            return ImageTk.PhotoImage(image)
        except Exception:
            self.logger.exception("No se pudo cargar el logo; se omite.")
            return None

    def _set_inputs_state(self, state: str) -> None:
        self.start_button.config(state=state)
        self.title_entry.config(state=state)
        self.description_text.config(state=state)
        self.privacy_public_radio.config(state=state)
        self.privacy_private_radio.config(state=state)

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
