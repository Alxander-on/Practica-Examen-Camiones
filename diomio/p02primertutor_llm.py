"""Tutor local de logística y seguridad vial (práctica introductoria LLM)."""

import os
import threading

import customtkinter as ctk
import ollama
from dotenv import load_dotenv

load_dotenv()


FONDO = "#080D0B"
PANEL = "#101915"
VERDE = "#8CFFC4"
SUAVE = "#227D3A"

PROMPT_PREDETERMINADO = (
    "Eres un asistente de logística y seguridad vial para estudiantes de ingeniería. "
    "Explica cómo tomar decisiones de acceso de camiones, inspección de carga y "
    "gestión de incidentes con ejemplos sencillos. Distingue siempre hechos, reglas "
    "e hipótesis; prioriza la seguridad de las personas y recomienda revisión humana "
    "cuando falten datos. Responde en español, de forma clara y breve."
)


class TutorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LogiSmart · Tutor LLM")
        self.geometry("1000x720")
        self.minsize(820, 600)
        self.configure(fg_color=FONDO)
        self.modelo = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.historial: list[dict[str, str]] = []
        self.ocupado = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        barra = ctk.CTkFrame(self, width=285, corner_radius=0, fg_color="#0B120E")
        barra.grid(row=0, column=0, sticky="nsw")
        barra.grid_propagate(False)
        ctk.CTkLabel(barra, text="◆  TUTOR LLM", text_color=VERDE,
                     font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=22, pady=(27, 5))
        ctk.CTkLabel(barra, text="CONFIGURACIÓN DEL SISTEMA",
                     text_color=SUAVE, font=("Segoe UI", 9, "bold")).pack(
                         anchor="w", padx=23, pady=(12, 5)
                     )
        self.txt_sistema = ctk.CTkTextbox(
            barra, width=245, height=260, fg_color=PANEL,
            font=("Segoe UI", 11), wrap="word",
        )
        self.txt_sistema.pack(padx=18, pady=6)
        self.txt_sistema.insert("1.0", PROMPT_PREDETERMINADO)
        ctk.CTkLabel(barra, text="MODELO OLLAMA", text_color=SUAVE,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=22, pady=(15, 5))
        self.ent_modelo = ctk.CTkEntry(barra, width=245)
        self.ent_modelo.pack(padx=18, pady=5)
        self.ent_modelo.insert(0, self.modelo)
        ctk.CTkLabel(
            barra, text="Ejemplo sugerido: llama3.2\nOllama debe estar ejecutándose.",
            text_color=SUAVE, justify="left", font=("Segoe UI", 10),
        ).pack(anchor="w", padx=22, pady=7)
        ctk.CTkButton(barra, text="Ver resumen de sesión", fg_color="#123C2A",
                      command=self.mostrar_resumen).pack(fill="x", padx=18, pady=12)

        contenido = ctk.CTkFrame(self, fg_color=FONDO, corner_radius=0)
        contenido.grid(row=0, column=1, sticky="nsew", padx=26, pady=25)
        contenido.grid_columnconfigure(0, weight=1)
        contenido.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(contenido, text="Tutor de logística y seguridad vial",
                     text_color="#E5F1E9", font=("Segoe UI", 23, "bold")).grid(
                         row=0, column=0, sticky="w", pady=(0, 14)
                     )
        self.chat = ctk.CTkTextbox(
            contenido, fg_color=PANEL, text_color="#E5F1E9",
            font=("Segoe UI", 12), wrap="word",
        )
        self.chat.grid(row=1, column=0, sticky="nsew")
        self.chat.insert("end", "Hola. Pregúntame sobre logística, control de acceso "
                         "o seguridad vial.\n\n")
        self.estado = ctk.CTkLabel(contenido, text="", text_color=SUAVE)
        self.estado.grid(row=2, column=0, sticky="w", pady=(8, 0))
        fila = ctk.CTkFrame(contenido, fg_color="transparent")
        fila.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        fila.grid_columnconfigure(0, weight=1)
        self.entrada = ctk.CTkEntry(
            fila, height=42, placeholder_text="Escribe tu pregunta y presiona Enter…"
        )
        self.entrada.grid(row=0, column=0, sticky="ew", padx=(0, 9))
        self.entrada.bind("<Return>", lambda _: self.enviar_mensaje())
        self.boton_enviar = ctk.CTkButton(
            fila, text="Enviar", width=115, height=42, command=self.enviar_mensaje
        )
        self.boton_enviar.grid(row=0, column=1)

    def enviar_mensaje(self) -> None:
        pregunta = self.entrada.get().strip()
        if not pregunta or self.ocupado:
            return
        prompt = self.txt_sistema.get("1.0", "end").strip()
        modelo = self.ent_modelo.get().strip()
        if not prompt or not modelo:
            self.estado.configure(text="Completa las instrucciones del sistema y el modelo.",
                                  text_color="#FFC857")
            return

        self.modelo = modelo
        self.historial.append({"role": "user", "content": pregunta})
        self.chat.insert("end", f"Tú: {pregunta}\n\n")
        self.chat.see("end")
        self.entrada.delete(0, "end")
        self.ocupado = True
        self.boton_enviar.configure(state="disabled", text="Pensando…")
        self.estado.configure(text=f"Consultando Ollama · {modelo}", text_color=VERDE)

        def consultar() -> None:
            try:
                mensajes = [{"role": "system", "content": prompt}, *self.historial]
                respuesta = ollama.chat(model=modelo, messages=mensajes)
                contenido = respuesta["message"]["content"].strip()
                if not contenido:
                    raise ValueError("Ollama devolvió una respuesta vacía.")
            except Exception as error:
                self.after(0, lambda error=error: self._fallo_consulta(error))
                return
            self.after(0, lambda: self._mostrar_respuesta(contenido))

        threading.Thread(target=consultar, daemon=True).start()

    def _mostrar_respuesta(self, contenido: str) -> None:
        self.historial.append({"role": "assistant", "content": contenido})
        self.chat.insert("end", f"Tutor: {contenido}\n\n{'─' * 55}\n\n")
        self.chat.see("end")
        self.ocupado = False
        self.boton_enviar.configure(state="normal", text="Enviar")
        self.estado.configure(text=f"Listo · {self.modelo}", text_color=VERDE)

    def _fallo_consulta(self, error: Exception) -> None:
        # La pregunta sigue visible, pero no entra al historial enviado al modelo.
        self.historial.pop()
        self.chat.insert(
            "end", "No se pudo conectar con Ollama. Verifica que el servicio esté "
            f"activo y que el modelo «{self.modelo}» esté instalado.\nDetalle: {error}\n\n"
        )
        self.chat.see("end")
        self.ocupado = False
        self.boton_enviar.configure(state="normal", text="Enviar")
        self.estado.configure(text="Ollama no disponible", text_color="#FF6B6B")

    def mostrar_resumen(self) -> None:
        preguntas = [item["content"] for item in self.historial if item["role"] == "user"]
        respuestas = sum(item["role"] == "assistant" for item in self.historial)
        resumen = [
            "RESUMEN DE LA SESIÓN",
            f"Preguntas realizadas: {len(preguntas)}",
            f"Respuestas recibidas: {respuestas}",
        ]
        if preguntas:
            resumen.extend(["", "Temas recientes:"])
            resumen.extend(f"• {pregunta}" for pregunta in preguntas[-3:])
        self.chat.insert("end", "\n" + "\n".join(resumen) + "\n\n")
        self.chat.see("end")


if __name__ == "__main__":
    TutorApp().mainloop()
