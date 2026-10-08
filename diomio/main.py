"""Interfaz principal de LogiSmart: navegación lateral, reglas y persistencia."""

import csv
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from dotenv import load_dotenv

load_dotenv()

from asistente_rag import AsistenteRAGLogiSmart
from clasificador_hibrido import ClasificadorHibrido
from conexion_db import MongoDBManager, cargar_datos_demo
from motor_reglas import MotorReglasLogistics


FONDO = "#010D08D9"
PANEL = "#101915"
PANEL_2 = "#16231C"
VERDE = "#A86539"
VERDE_OSCURO = "#123C2A"
TEXTO = "#E5F1E9"
SUAVE = "#91A99A"
ROJO = "#FF6B6B"
AMBAR = "#FFC857"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class LogiSmartApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LogiSmart | Centro de operaciones")
        self.geometry("1280x820")
        self.minsize(1060, 700)
        self.configure(fg_color=FONDO)

        self.db = MongoDBManager()
        self.motor = MotorReglasLogistics()
        self.clasificador = ClasificadorHibrido(
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
            model_name=os.getenv("OLLAMA_MODEL", "llama3.2"),
        )
        self.clasificador.modo_simulacion = os.getenv(
            "MODO_SIMULACION_CORREO", "false"
        ).lower() in {"1", "true", "sí", "si"}
        umbral = os.getenv("UMBRAL_REVISION", "ALTA").upper()
        if umbral in {"BAJA", "MEDIA", "ALTA", "CRITICA"}:
            self.clasificador.umbral_revision = umbral
        self.asistente = AsistenteRAGLogiSmart(
            self.db, self.clasificador.ollama_url, self.clasificador.model_name
        )
        self.pagina_actual = "Resumen"
        self._risk_canvas: FigureCanvasTkAgg | None = None
        self._risk_summary_label: Any = None
        self._incidente_seleccionado: str | None = None
        self._riesgo_seleccionado: str | None = None
        self._page_generation = 0
        self._build_shell()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self._encabezado("Preparando LogiSmart…", "Cargando datos de demostración y conexión")
        def iniciar() -> None:
            cargar_datos_demo(self.db)
        def mostrar_inicio(_: Any = None) -> None:
            self.mostrar_pagina("Resumen")
        def error_inicio(error: Exception) -> None:
            messagebox.showerror("No se pudieron cargar los datos iniciales", str(error), parent=self)
            self.mostrar_pagina("Resumen")
        self._trabajo(iniciar, mostrar_inicio, error_inicio)

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=225, corner_radius=0, fg_color="#0B120E")
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(
            self.sidebar, text="◆  LOGISMART", text_color=VERDE,
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w", padx=22, pady=(28, 4))
        ctk.CTkLabel(
            self.sidebar, text="CENTRO DE OPERACIONES", text_color=SUAVE,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=24, pady=(0, 25))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        opciones = [
            ("Resumen", "▦  Resumen"),
            ("Camiones", "▰  Camiones"),
            ("Control de acceso", "◈  Control de acceso"),
            ("Incidentes", "◎  Incidentes"),
            ("Asistente RAG", "✳  Asistente RAG"),
            ("Riesgos éticos", "△  Riesgos éticos"),
            ("Reportes", "▤  Reportes"),
            ("Configuración", "⚙  Configuración"),
        ]
        for nombre, texto in opciones:
            boton = ctk.CTkButton(
                self.sidebar, text=texto, anchor="w", height=42, corner_radius=9,
                fg_color="transparent", hover_color=PANEL_2,
                text_color=SUAVE, font=("Segoe UI", 12),
                command=lambda pagina=nombre: self.mostrar_pagina(pagina),
            )
            boton.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[nombre] = boton

        ctk.CTkFrame(self.sidebar, height=2, fg_color=PANEL_2).pack(
            fill="x", padx=17, pady=(24, 13)
        )
        self.lbl_db_status = ctk.CTkLabel(
            self.sidebar, text="", text_color=SUAVE, justify="left",
            font=("Segoe UI", 10),
        )
        self.lbl_db_status.pack(anchor="w", padx=21, pady=5)
        ctk.CTkButton(
            self.sidebar, text="Abrir tutor P02 ↗", anchor="w", height=38,
            fg_color=VERDE_OSCURO, hover_color="#1C5C3D",
            command=self.abrir_tutor,
        ).pack(side="bottom", fill="x", padx=14, pady=18)
        self.contenido = ctk.CTkFrame(self, fg_color=FONDO, corner_radius=0)
        self.contenido.grid(row=0, column=1, sticky="nsew")
        self._actualizar_estado_db()

    def _actualizar_estado_db(self) -> None:
        if self.db.esta_conectado():
            self.lbl_db_status.configure(text=f"●  MongoDB conectado\n    {self.db.db_name}",
                                         text_color=VERDE)
        else:
            self.lbl_db_status.configure(text="●  MongoDB desconectado\n    Configurar conexión",
                                         text_color=AMBAR)

    def _encabezado(self, titulo: str, descripcion: str) -> None:
        cabecera = ctk.CTkFrame(self.contenido, fg_color="transparent")
        cabecera.pack(fill="x", padx=30, pady=(27, 15))
        ctk.CTkLabel(cabecera, text=titulo, text_color=TEXTO,
                     font=("Segoe UI", 25, "bold")).pack(anchor="w")
        ctk.CTkLabel(cabecera, text=descripcion, text_color=SUAVE,
                     font=("Segoe UI", 12)).pack(anchor="w", pady=(4, 0))

    def _limpiar_pagina(self) -> None:
        for widget in self.contenido.winfo_children():
            widget.destroy()
        self._risk_canvas = None
        self._risk_summary_label = None

    def mostrar_pagina(self, pagina: str) -> None:
        self._page_generation += 1
        self.pagina_actual = pagina
        for nombre, boton in self.nav_buttons.items():
            boton.configure(
                fg_color=VERDE_OSCURO if nombre == pagina else "transparent",
                text_color=VERDE if nombre == pagina else SUAVE,
            )
        self._limpiar_pagina()
        vistas: dict[str, Callable[[], None]] = {
            "Resumen": self._pagina_resumen,
            "Camiones": self._pagina_camiones,
            "Control de acceso": self._pagina_acceso,
            "Incidentes": self._pagina_incidentes,
            "Asistente RAG": self._pagina_rag,
            "Riesgos éticos": self._pagina_riesgos,
            "Reportes": self._pagina_reportes,
            "Configuración": self._pagina_configuracion,
        }
        vistas[pagina]()

    def _card(self, parent: Any, title: str, value: str, accent: str = VERDE) -> Any:
        card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        ctk.CTkLabel(card, text=title.upper(), text_color=SUAVE,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(card, text=value, text_color=accent,
                     font=("Segoe UI", 28, "bold")).pack(anchor="w", padx=18, pady=(0, 16))
        return card

    def _tabla(self, parent: Any, columnas: list[tuple[str, str, int]]) -> ttk.Treeview:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Logi.Treeview", background=PANEL, foreground=TEXTO,
            fieldbackground=PANEL, rowheight=31, borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Logi.Treeview.Heading", background=PANEL_2, foreground=VERDE,
            relief="flat", font=("Segoe UI", 10, "bold"),
        )
        style.map("Logi.Treeview", background=[("selected", VERDE_OSCURO)])
        keys = [c[0] for c in columnas]
        tabla = ttk.Treeview(parent, columns=keys, show="headings", style="Logi.Treeview")
        for key, titulo, width in columnas:
            tabla.heading(key, text=titulo)
            tabla.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=scroll.set)
        tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tabla

    def _trabajo(
        self, funcion: Callable[[], Any], al_terminar: Callable[[Any], None],
        al_fallar: Callable[[Exception], None] | None = None,
    ) -> None:
        generacion = self._page_generation
        def entregar(callback: Callable[[], None]) -> None:
            if generacion == self._page_generation and self.winfo_exists():
                callback()
        def reportar_error(error: Exception) -> None:
            if not self.winfo_exists():
                return
            if generacion == self._page_generation and al_fallar:
                al_fallar(error)
            else:
                messagebox.showerror("No se pudo completar", str(error), parent=self)
        def ejecutar() -> None:
            try:
                resultado = funcion()
            except Exception as error:
                self.after(0, lambda error=error: reportar_error(error))
                return
            self.after(0, lambda: entregar(lambda: al_terminar(resultado)))
        threading.Thread(target=ejecutar, daemon=True).start()

    def _pagina_resumen(self) -> None:
        self._encabezado("Resumen operativo", "Indicadores y actividad reciente")
        filtros = ctk.CTkFrame(self.contenido, fg_color="transparent")
        filtros.pack(fill="x", padx=30, pady=(0, 12))
        desde = ctk.CTkEntry(filtros, width=155, placeholder_text="Desde AAAA-MM-DD")
        hasta = ctk.CTkEntry(filtros, width=155, placeholder_text="Hasta AAAA-MM-DD")
        desde.pack(side="left", padx=(0, 8))
        hasta.pack(side="left", padx=8)
        valores = ctk.CTkFrame(self.contenido, fg_color="transparent")
        valores.pack(fill="x", padx=24, pady=5)
        contenedor = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        contenedor.pack(fill="both", expand=True, padx=30, pady=15)
        ctk.CTkLabel(contenedor, text="Incidentes por categoría y semana ISO",
                     text_color=TEXTO, font=("Segoe UI", 14, "bold")).pack(
                         anchor="w", padx=18, pady=14)
        tabla = self._tabla(contenedor, [
            ("categoria", "Categoría", 190), ("semana", "Año-semana", 160),
            ("total", "Incidentes", 120),
        ])

        def cargar(desde_texto: str, hasta_texto: str) -> None:
            try:
                fecha_desde = datetime.strptime(desde_texto, "%Y-%m-%d") if desde_texto else None
                fecha_hasta = datetime.strptime(hasta_texto, "%Y-%m-%d") if hasta_texto else None
                incidentes = self.db.obtener_incidentes()
                riesgos = self.db.obtener_riesgos()
                accesos = self.db.obtener_historial_accesos()
                agregacion = self.db.agregacion_incidentes_semana(fecha_desde, fecha_hasta)

                def dentro(registro: dict[str, Any], campo: str) -> bool:
                    fecha = registro.get(campo)
                    if isinstance(fecha, datetime):
                        fecha = fecha.replace(tzinfo=None)
                        return (fecha_desde is None or fecha >= fecha_desde) and (
                            fecha_hasta is None or fecha.date() <= fecha_hasta.date()
                        )
                    return fecha_desde is None and fecha_hasta is None

                atendidos = {
                    x.get("camion_id") for x in accesos
                    if x.get("camion_id") and dentro(x, "marca_tiempo")
                }
                return (
                    len(atendidos), sum(1 for x in accesos if dentro(x, "marca_tiempo")),
                    sum(1 for x in incidentes if x.get("estado") != "cerrado"
                        and dentro(x, "fecha_recepcion")),
                    sum(1 for x in riesgos if x.get("puntaje_inicial", 0) >= 15
                        and dentro(x, "fecha")),
                    [x for x in agregacion],
                )
            except ValueError as error:
                raise ValueError("Usa el formato de fecha AAAA-MM-DD.") from error

        def mostrar(datos: Any) -> None:
            for widget in valores.winfo_children():
                widget.destroy()
            titulos = ["Camiones atendidos", "Accesos registrados", "Incidentes abiertos",
                       "Riesgos críticos"]
            for titulo, value, color in zip(titulos, datos[:4],
                                           [VERDE, VERDE, AMBAR, ROJO]):
                self._card(valores, titulo, str(value), color).pack(
                    side="left", fill="x", expand=True, padx=6
                )
            for row in tabla.get_children():
                tabla.delete(row)
            for item in datos[4]:
                etiqueta = item["_id"]
                semana = f"{etiqueta.get('anio', '-')}–W{etiqueta.get('semana', '-')}"
                tabla.insert("", "end", values=(etiqueta.get("categoria", "Sin categoría"),
                                                semana, item.get("total", 0)))

        def aplicar_filtros() -> None:
            desde_texto, hasta_texto = desde.get().strip(), hasta.get().strip()
            self._trabajo(lambda: cargar(desde_texto, hasta_texto), mostrar)
        ctk.CTkButton(filtros, text="Aplicar filtros / actualizar", fg_color=VERDE_OSCURO,
                      command=aplicar_filtros).pack(side="left", padx=8)
        aplicar_filtros()

    def _pagina_camiones(self) -> None:
        self._encabezado("Flota de camiones", "Alta, consulta y baja de unidades")
        form = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        form.pack(fill="x", padx=30, pady=(0, 14))
        entradas: dict[str, ctk.CTkEntry] = {}
        for i, (clave, etiqueta) in enumerate([
            ("camion_id", "ID (CAM-104)"), ("placa", "Placa"), ("empresa", "Empresa")
        ]):
            ent = ctk.CTkEntry(form, placeholder_text=etiqueta, width=205)
            ent.grid(row=0, column=i, padx=10, pady=14)
            entradas[clave] = ent
        autorizado = ctk.CTkSwitch(form, text="Autorizado")
        certificado = ctk.CTkSwitch(form, text="Certificación vigente")
        autorizado.select()
        certificado.select()
        autorizado.grid(row=1, column=0, padx=12, pady=(0, 14), sticky="w")
        certificado.grid(row=1, column=1, padx=12, pady=(0, 14), sticky="w")
        cuerpo = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        cuerpo.pack(fill="both", expand=True, padx=30, pady=(0, 25))
        tabla = self._tabla(cuerpo, [
            ("id", "ID", 160), ("placa", "Placa", 150),
            ("empresa", "Empresa", 230), ("autorizacion", "Autorizado", 120),
            ("cert", "Certificación", 140),
        ])
        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=0, column=3, rowspan=2, padx=12, pady=10)
        camion_seleccionado: dict[str, str | None] = {"id": None}

        def mostrar_camiones(filas: list[dict[str, Any]]) -> None:
            tabla.delete(*tabla.get_children())
            for row in filas:
                tabla.insert("", "end", iid=str(row["_id"]), values=(
                    row.get("camion_id", ""), row.get("placa", ""), row.get("empresa", ""),
                    "Sí" if row.get("autorizacion") else "No",
                    "Sí" if row.get("cert_conductor") else "No",
                ))
        def recargar() -> None:
            self._trabajo(self.db.listar_camiones, mostrar_camiones)
        def guardar() -> None:
            datos = {key: entradas[key].get().strip() for key in entradas}
            autorizado_valor, certificado_valor = bool(autorizado.get()), bool(certificado.get())
            if not all(datos.values()):
                messagebox.showwarning("Datos incompletos", "Completa ID, placa y empresa.", parent=self)
                return
            camion_anterior = camion_seleccionado["id"]
            if camion_anterior:
                funcion = lambda: self.db.actualizar_camion(
                    camion_anterior, datos["camion_id"], datos["placa"],
                    datos["empresa"], autorizado_valor, certificado_valor,
                )
            else:
                funcion = lambda: self.db.registrar_camion(
                    datos["camion_id"], datos["placa"], datos["empresa"],
                    autorizado_valor, certificado_valor,
                )
            def guardado(_: Any) -> None:
                camion_seleccionado["id"] = None
                recargar()
                messagebox.showinfo("Guardado", "Camión guardado.", parent=self)
            self._trabajo(funcion, guardado)
        def borrar() -> None:
            seleccionado = tabla.selection()
            if not seleccionado:
                messagebox.showwarning("Selecciona un camión", "Elige una fila de la tabla.", parent=self)
                return
            camion_id = tabla.item(seleccionado[0], "values")[0]
            if messagebox.askyesno("Eliminar camión", f"¿Eliminar {camion_id}?", parent=self):
                self._trabajo(lambda: self.db.eliminar_camion(camion_id),
                              lambda _: (camion_seleccionado.update({"id": None}), recargar()))
        def nuevo() -> None:
            camion_seleccionado["id"] = None
            for entry in entradas.values():
                entry.delete(0, "end")
            autorizado.select()
            certificado.select()
            tabla.selection_remove(*tabla.selection())
        ctk.CTkButton(btns, text="Guardar / actualizar", command=guardar).pack(pady=4)
        ctk.CTkButton(btns, text="Nuevo camión", fg_color=PANEL_2,
                      command=nuevo).pack(pady=4)
        ctk.CTkButton(btns, text="Eliminar seleccionado", fg_color="#622D2D",
                      hover_color="#843737", command=borrar).pack(pady=4)
        def seleccionar_camion(_: Any = None) -> None:
            selection = tabla.selection()
            if selection:
                camion_seleccionado["id"] = tabla.item(selection[0], "values")[0]
                self._cargar_camion_seleccionado(
                    tabla, entradas, autorizado, certificado
                )
        tabla.bind("<<TreeviewSelect>>", seleccionar_camion)
        recargar()

    @staticmethod
    def _cargar_camion_seleccionado(
        tabla: Any, entradas: dict[str, Any], autorizado: Any, certificado: Any
    ) -> None:
        selection = tabla.selection()
        if not selection:
            return
        values = tabla.item(selection[0], "values")
        for key, value in zip(("camion_id", "placa", "empresa"), values[:3]):
            entradas[key].delete(0, "end")
            entradas[key].insert(0, value)
        (autorizado.select if values[3] == "Sí" else autorizado.deselect)()
        (certificado.select if values[4] == "Sí" else certificado.deselect)()

    def _pagina_acceso(self) -> None:
        self._encabezado("Control de acceso", "Evalúa las premisas; los resultados se actualizan en vivo")
        principal = ctk.CTkFrame(self.contenido, fg_color="transparent")
        principal.pack(fill="both", expand=True, padx=30, pady=(0, 24))
        panel = ctk.CTkFrame(principal, fg_color=PANEL, corner_radius=14)
        panel.pack(side="left", fill="y", padx=(0, 12))
        lateral = ctk.CTkFrame(principal, fg_color="transparent")
        lateral.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(panel, text="PREMISAS", text_color=VERDE,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
        camion = ctk.CTkEntry(panel, width=260, placeholder_text="ID o placa del camión")
        camion.pack(padx=14, pady=8)
        operador = ctk.CTkEntry(panel, width=260, placeholder_text="Nombre del operador")
        operador.pack(padx=14, pady=(0, 8))
        self._campo_camion_acceso = camion
        self._campo_operador_acceso = operador
        switches: dict[str, Any] = {}
        for clave, texto, seleccionado in [
            ("P", "P · Autorización vigente", True),
            ("Q", "Q · Anomalía reportada", False),
            ("R", "R · Carga prioritaria", False),
            ("S", "S · Sello intacto", True),
            ("C", "C · Certificación vigente", True),
            ("M", "M · Material peligroso", False),
            ("H", "H · Horario restringido", False),
        ]:
            control = ctk.CTkSwitch(
                panel, text=texto, command=self._actualizar_vista_acceso,
            )
            if seleccionado:
                control.select()
            control.pack(anchor="w", padx=18, pady=5)
            switches[clave] = control
        resultado = ctk.CTkFrame(lateral, fg_color=PANEL, corner_radius=14)
        resultado.pack(fill="x", pady=(0, 12))
        self.lbl_resultado_acceso = ctk.CTkLabel(
            resultado, text="", text_color=VERDE, font=("Segoe UI", 20, "bold")
        )
        self.lbl_resultado_acceso.pack(anchor="w", padx=18, pady=(15, 4))
        self.txt_explicacion = ctk.CTkTextbox(
            resultado, height=165, fg_color="#0B120E", text_color=TEXTO,
            font=("Consolas", 11),
        )
        self.txt_explicacion.pack(fill="x", padx=14, pady=(4, 14))
        ctk.CTkLabel(lateral, text="Tabla de verdad base (A y E)",
                     text_color=TEXTO, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=7)
        tabla = self._tabla(lateral, [(x, x, 55) for x in ("P", "Q", "R", "S", "A", "E")])
        for row in self.motor.generar_tabla_verdad():
            tabla.insert("", "end", values=tuple(row[k] for k in ("P", "Q", "R", "S", "A", "E")))
        self._switches_acceso = switches
        self.lbl_camion_encontrado = ctk.CTkLabel(
            panel, text="", text_color=SUAVE, wraplength=255, justify="left",
            font=("Segoe UI", 10),
        )
        self.lbl_camion_encontrado.pack(anchor="w", padx=16, pady=(4, 0))
        ctk.CTkButton(
            panel, text="Buscar unidad y completar P/C", fg_color=PANEL_2,
            command=self._buscar_camion_acceso,
        ).pack(fill="x", padx=14, pady=(8, 0))
        camion.bind("<Return>", lambda _: self._buscar_camion_acceso())
        self._actualizar_vista_acceso()
        ctk.CTkButton(panel, text="Registrar decisión", fg_color=VERDE_OSCURO,
                      command=self._guardar_acceso).pack(fill="x", padx=14, pady=15)
        ctk.CTkButton(
            lateral, text="Ver bitácora reciente", fg_color=PANEL_2,
            command=self._mostrar_historial_accesos,
        ).pack(anchor="e", pady=(2, 5))

    def _resultado_acceso_actual(self) -> dict[str, Any]:
        valores = {k: bool(v.get()) for k, v in self._switches_acceso.items()}
        return self.motor.evaluar_acceso(**valores)

    def _actualizar_vista_acceso(self) -> None:
        if not hasattr(self, "_switches_acceso"):
            return
        resultado = self._resultado_acceso_actual()
        texto = f"{'PERMITIDO' if resultado['A'] else 'DENEGADO'}  ·  " \
                f"{'INSPECCIÓN REQUERIDA' if resultado['E'] else 'SIN INSPECCIÓN'}"
        self.lbl_resultado_acceso.configure(
            text=texto, text_color=VERDE if resultado["A"] and not resultado["E"] else AMBAR
        )
        self.txt_explicacion.delete("1.0", "end")
        self.txt_explicacion.insert("end", resultado["explicacion"])

    def _buscar_camion_acceso(self) -> None:
        identificador = self._campo_camion_acceso.get().strip()
        if not identificador:
            messagebox.showwarning("Escribe una unidad", "Ingresa un ID o placa para buscar.", parent=self)
            return
        def mostrar(camion: dict[str, Any] | None) -> None:
            if camion is None:
                self.lbl_camion_encontrado.configure(
                    text="No se encontró la unidad; regístrala en Camiones.",
                    text_color=AMBAR,
                )
                return
            for clave, campo in (
                ("P", "autorizacion"), ("C", "cert_conductor")
            ):
                control = self._switches_acceso[clave]
                (control.select if camion.get(campo) else control.deselect)()
            self.lbl_camion_encontrado.configure(
                text=f"{camion.get('camion_id')} · {camion.get('placa')} · "
                     f"{camion.get('empresa')}\nAutorización y certificación precargadas.",
                text_color=VERDE,
            )
            self._actualizar_vista_acceso()
        self._trabajo(lambda: self.db.obtener_camion(identificador), mostrar)

    def _mostrar_historial_accesos(self) -> None:
        ventana = ctk.CTkToplevel(self)
        ventana.title("Bitácora de accesos")
        ventana.geometry("900x640")
        ventana.configure(fg_color=FONDO)
        ctk.CTkLabel(ventana, text="Decisiones recientes", text_color=VERDE,
                     font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=20, pady=14)
        marco = ctk.CTkFrame(ventana, fg_color=PANEL, corner_radius=12)
        marco.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        tabla = self._tabla(marco, [
            ("camion", "Camión", 120), ("A", "Acceso A", 90), ("E", "Inspección E", 100),
            ("operador", "Operador", 145), ("fecha", "Fecha UTC", 180),
        ])
        edicion = ctk.CTkFrame(ventana, fg_color="transparent")
        edicion.pack(fill="x", padx=20, pady=(0, 16))
        operador_edit = ctk.CTkEntry(edicion, placeholder_text="Operador", width=220)
        operador_edit.pack(anchor="w", pady=(0, 7))
        detalle = ctk.CTkTextbox(edicion, height=100, fg_color=PANEL, text_color=TEXTO)
        detalle.pack(fill="x")
        selected_id: dict[str, str | None] = {"id": None}
        cache: dict[str, dict[str, Any]] = {}
        def mostrar(accesos: list[dict[str, Any]]) -> None:
            tabla.delete(*tabla.get_children())
            cache.clear()
            for registro in accesos:
                cache[str(registro["_id"])] = registro
                resultados = registro.get("resultados", {})
                tabla.insert("", "end", iid=str(registro["_id"]), values=(
                    registro.get("camion_id", ""),
                    "Sí" if resultados.get("A") else "No",
                    "Sí" if resultados.get("E") else "No",
                    registro.get("operador", ""),
                    str(registro.get("marca_tiempo", ""))[:19],
                ))
            def seleccionar(_: Any = None) -> None:
                selection = tabla.selection()
                if not selection:
                    return
                registro = cache.get(selection[0], {})
                selected_id["id"] = selection[0]
                operador_edit.delete(0, "end")
                operador_edit.insert(0, registro.get("operador", ""))
                detalle.delete("1.0", "end")
                detalle.insert("end", registro.get("explicacion", "Sin explicación registrada."))
            tabla.bind("<<TreeviewSelect>>", seleccionar)
        def actualizar() -> None:
            registro_id = selected_id["id"]
            if not registro_id:
                messagebox.showwarning("Selecciona una decisión", "Elige un registro de la bitácora.", parent=ventana)
                return
            operador_valor = operador_edit.get().strip()
            explicacion_valor = detalle.get("1.0", "end").strip()
            self._trabajo(
                lambda: self.db.actualizar_acceso(
                    registro_id, operador_valor, explicacion_valor
                ),
                lambda _: self._trabajo(self.db.obtener_historial_accesos, mostrar),
            )
        def eliminar() -> None:
            registro_id = selected_id["id"]
            if not registro_id:
                messagebox.showwarning("Selecciona una decisión", "Elige un registro de la bitácora.", parent=ventana)
                return
            if messagebox.askyesno("Eliminar decisión", "¿Eliminar este registro de auditoría?", parent=ventana):
                self._trabajo(
                    lambda: self.db.eliminar_acceso(registro_id),
                    lambda _: self._trabajo(self.db.obtener_historial_accesos, mostrar),
                )
        botones = ctk.CTkFrame(edicion, fg_color="transparent")
        botones.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(botones, text="Guardar cambios", command=actualizar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(botones, text="Eliminar registro", fg_color="#622D2D",
                      hover_color="#843737", command=eliminar).pack(side="left")
        self._trabajo(self.db.obtener_historial_accesos, mostrar)

    def _guardar_acceso(self) -> None:
        camion_id = self._campo_camion_acceso.get().strip()
        if not camion_id:
            messagebox.showwarning("Falta la unidad", "Escribe el ID o la placa del camión.", parent=self)
            return
        valores = {k: bool(v.get()) for k, v in self._switches_acceso.items()}
        resultado = self._resultado_acceso_actual()
        operador = self._campo_operador_acceso.get().strip()
        def guardar() -> Any:
            camion = self.db.obtener_camion(camion_id)
            if camion is None:
                raise ValueError("La unidad no está registrada. Agrégala primero en Camiones.")
            return self.db.registrar_acceso(
                camion["camion_id"], valores["P"], valores["Q"], valores["R"], valores["S"],
                resultado["A"], resultado["E"], resultado["explicacion"],
                operador, C=valores["C"], M=valores["M"], H=valores["H"],
            )
        self._trabajo(
            guardar,
            lambda _: messagebox.showinfo("Bitácora", "Decisión registrada en MongoDB.", parent=self),
        )

    def _pagina_incidentes(self) -> None:
        self._encabezado("Bandeja de incidentes", "Clasifica correos con reglas + Ollama, revisa y actualiza estados")
        superior = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        superior.pack(fill="x", padx=30, pady=(0, 14))
        correo = ctk.CTkTextbox(superior, height=90, fg_color="#0B120E", text_color=TEXTO)
        correo.pack(fill="x", padx=14, pady=(14, 7))
        acciones = ctk.CTkFrame(superior, fg_color="transparent")
        acciones.pack(fill="x", padx=14, pady=(2, 12))
        fila_edicion = ctk.CTkFrame(acciones, fg_color="transparent")
        fila_edicion.pack(fill="x", pady=(0, 5))
        fila_botones = ctk.CTkFrame(acciones, fg_color="transparent")
        fila_botones.pack(fill="x")
        salida = ctk.CTkTextbox(superior, height=105, fg_color="#0B120E", text_color=SUAVE)
        salida.pack(fill="x", padx=14, pady=(0, 12))
        panel = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        panel.pack(fill="both", expand=True, padx=30, pady=(0, 25))
        tabla = self._tabla(panel, [
            ("id", "ID", 145), ("categoria", "Categoría", 145),
            ("prioridad", "Prioridad", 100), ("estado", "Estado", 120),
            ("fecha", "Recibido", 160), ("revision", "Revisión humana", 130),
        ])
        estado = ctk.CTkOptionMenu(fila_edicion, values=["nuevo", "en_atencion", "cerrado"])
        estado.pack(side="left", padx=(0, 8))
        categoria_edit = ctk.CTkOptionMenu(
            fila_edicion, values=["Mecánico", "Documentación", "Seguridad", "Retraso", "Otro"]
        )
        categoria_edit.pack(side="left", padx=5)
        prioridad_edit = ctk.CTkOptionMenu(
            fila_edicion, values=["BAJA", "MEDIA", "ALTA", "CRITICA"]
        )
        prioridad_edit.pack(side="left", padx=5)
        resumen_edit = ctk.CTkEntry(fila_edicion, placeholder_text="Resumen editable", width=300)
        resumen_edit.pack(side="left", padx=5, fill="x", expand=True)

        def mostrar_cache(items: list[dict[str, Any]]) -> None:
            self._incidentes_cache = items
            tabla.delete(*tabla.get_children())
            for item in items:
                clasif = item.get("clasificacion", {})
                tabla.insert("", "end", iid=str(item["_id"]), values=(
                    str(item["_id"])[-8:], clasif.get("categoria", "Otro"),
                    clasif.get("prioridad", "-"), item.get("estado", "nuevo"),
                    str(item.get("fecha_recepcion", ""))[:16],
                    "Sí" if clasif.get("requiere_revision_humana") else "No",
                ))
        def refrescar() -> None:
            self._trabajo(self.db.obtener_incidentes, mostrar_cache)

        def clasificar() -> None:
            texto = correo.get("1.0", "end").strip()
            if not texto:
                messagebox.showwarning("Correo vacío", "Pega el correo a clasificar.", parent=self)
                return
            btn_clasificar.configure(state="disabled", text="Clasificando…")
            def proceso() -> Any:
                resultado = self.clasificador.procesar_incidente(texto)
                try:
                    self.db.guardar_incidente(
                        texto, resultado, resultado.get("entidades", []),
                    )
                    self.db.registrar_evaluacion_llm(
                        texto, resultado, self.clasificador.model_name,
                        resultado.get("latencia", 0),
                        resultado.get("origen", "").endswith("coincidencia)"),
                    )
                except Exception as error:
                    return resultado, str(error)
                return resultado, None
            def listo(resultado: Any) -> None:
                btn_clasificar.configure(state="normal", text="Clasificar y guardar")
                salida.delete("1.0", "end")
                clasificacion, error_guardado = resultado
                salida.insert("end", json.dumps(clasificacion, ensure_ascii=False, indent=2))
                if error_guardado:
                    salida.insert("end", f"\n\nNo se persistió en MongoDB: {error_guardado}")
                else:
                    refrescar()
            def error(exc: Exception) -> None:
                btn_clasificar.configure(state="normal", text="Clasificar y guardar")
                messagebox.showerror("No se guardó el incidente", str(exc), parent=self)
            self._trabajo(proceso, listo, error)

        def seleccionar(_: Any = None) -> None:
            selection = tabla.selection()
            if not selection:
                return
            registro = next(
                (x for x in self._incidentes_cache if str(x["_id"]) == selection[0]), None
            )
            if not registro:
                return
            self._incidente_seleccionado = selection[0]
            clasif = registro.get("clasificacion", {})
            estado.set(registro.get("estado", "nuevo"))
            categoria_edit.set(clasif.get("categoria", "Otro"))
            prioridad_edit.set(clasif.get("prioridad", "BAJA"))
            resumen_edit.delete(0, "end")
            resumen_edit.insert(0, clasif.get("resumen", ""))
            salida.delete("1.0", "end")
            salida.insert("end", registro.get("correo_original", ""))
            salida.insert("end", "\n\nHistorial de estados:\n")
            salida.insert("end", json.dumps(registro.get("historial", []), default=str, ensure_ascii=False))
        def guardar_edicion() -> None:
            if not self._incidente_seleccionado:
                messagebox.showwarning("Selecciona un incidente", "Elige una fila para editar.", parent=self)
                return
            registro = next((x for x in self._incidentes_cache
                             if str(x["_id"]) == self._incidente_seleccionado), {})
            clasif = dict(registro.get("clasificacion", {}))
            clasif.update({
                "categoria": categoria_edit.get(), "prioridad": prioridad_edit.get(),
                "resumen": resumen_edit.get().strip(),
            })
            incidente_id = self._incidente_seleccionado
            nuevo_estado = estado.get()
            self._trabajo(
                lambda: self.db.actualizar_incidente(
                    incidente_id, clasif, nuevo_estado
                ),
                lambda _: refrescar(),
            )
        def eliminar() -> None:
            if not self._incidente_seleccionado:
                messagebox.showwarning("Selecciona un incidente", "Elige una fila para eliminar.", parent=self)
                return
            if messagebox.askyesno("Eliminar", "¿Eliminar permanentemente el incidente?", parent=self):
                incidente_id = self._incidente_seleccionado
                self._trabajo(
                    lambda: self.db.eliminar_incidente(incidente_id),
                    lambda _: (setattr(self, "_incidente_seleccionado", None), refrescar()),
                )
        def ejecutar_experimento() -> None:
            btn_experimento.configure(state="disabled", text="Evaluando 30 correos…")
            salida.delete("1.0", "end")
            salida.insert("end", "Ejecutando evaluación etiquetada; Ollama puede tardar unos minutos.\n")
            def mostrar_metricas(datos: dict[str, Any]) -> None:
                btn_experimento.configure(state="normal", text="Evaluar 30 correos")
                salida.delete("1.0", "end")
                salida.insert("end", f"Muestras evaluadas: {datos['muestras']}\n")
                salida.insert(
                    "end",
                    "Ollama/modelo: disponible\n" if datos["llm_disponible"]
                    else "Ollama/modelo: no disponible; se registra «Sin predicción» para LLM\n",
                )
                salida.insert("end", json.dumps(
                    datos["metricas"], ensure_ascii=False, indent=2
                ))
            def error_experimento(error: Exception) -> None:
                btn_experimento.configure(state="normal", text="Evaluar 30 correos")
                messagebox.showerror("Falló la evaluación", str(error), parent=self)
            self._trabajo(
                self.clasificador.ejecutar_experimento_30_correos,
                mostrar_metricas, error_experimento,
            )
        btn_clasificar = ctk.CTkButton(
            fila_botones, text="Clasificar y guardar", command=clasificar,
        )
        btn_clasificar.pack(side="left", padx=4)
        ctk.CTkButton(fila_botones, text="Guardar edición", fg_color=VERDE_OSCURO,
                      command=guardar_edicion).pack(side="left", padx=4)
        ctk.CTkButton(fila_botones, text="Eliminar", fg_color="#622D2D",
                      hover_color="#843737", command=eliminar).pack(side="left", padx=4)
        btn_experimento = ctk.CTkButton(
            fila_botones, text="Evaluar 30 correos", fg_color=PANEL_2,
            command=ejecutar_experimento,
        )
        btn_experimento.pack(side="right", padx=4)
        tabla.bind("<<TreeviewSelect>>", seleccionar)
        refrescar()

    def _pagina_rag(self) -> None:
        self._encabezado("Asistente explicativo", "Consulta primero MongoDB; las respuestas incluyen referencias de origen")
        historial = ctk.CTkTextbox(
            self.contenido, fg_color=PANEL, text_color=TEXTO,
            font=("Segoe UI", 12), wrap="word",
        )
        historial.pack(fill="both", expand=True, padx=30, pady=(0, 12))
        historial.insert("end", "Asistente LogiSmart · Solo responde con información recuperada.\n\n")
        fila = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila.pack(fill="x", padx=30, pady=(0, 25))
        pregunta = ctk.CTkEntry(fila, placeholder_text="Ej.: ¿Por qué CAM-102 fue enviado a inspección?")
        pregunta.pack(side="left", fill="x", expand=True, padx=(0, 10))
        def enviar() -> None:
            texto = pregunta.get().strip()
            if not texto:
                return
            historial.insert("end", f"Tú: {texto}\nAsistente: Consultando MongoDB y Ollama…\n\n")
            historial.see("end")
            boton.configure(state="disabled", text="Consultando…")
            def listo(resultado: Any) -> None:
                boton.configure(state="normal", text="Preguntar")
                pregunta.delete(0, "end")
                fuentes = "\n".join(f"  • {f}" for f in resultado["fuentes"]) or "  • Sin registros coincidentes"
                historial.insert("end", f"Asistente: {resultado['respuesta']}\nFuentes:\n{fuentes}\n\n")
                historial.see("end")
            self._trabajo(
                lambda: self.asistente.responder_consulta(texto), listo,
                lambda error: (boton.configure(state="normal", text="Preguntar"),
                               messagebox.showerror("Consulta fallida", str(error), parent=self)),
            )
        boton = ctk.CTkButton(fila, text="Preguntar", command=enviar, width=125)
        boton.pack(side="right")
        pregunta.bind("<Return>", lambda _: enviar())

    def _pagina_riesgos(self) -> None:
        self._encabezado("Matriz de riesgos éticos", "Probabilidad × impacto y riesgo residual después de mitigar")
        panel = ctk.CTkFrame(self.contenido, fg_color="transparent")
        panel.pack(fill="both", expand=True, padx=30, pady=(0, 25))
        form = ctk.CTkFrame(panel, fg_color=PANEL, corner_radius=14, width=320)
        form.pack(side="left", fill="y", padx=(0, 12))
        visual = ctk.CTkFrame(panel, fg_color=PANEL, corner_radius=14)
        visual.pack(side="left", fill="both", expand=True)
        fields: dict[str, Any] = {}
        for clave, etiqueta in [
            ("modulo", "Módulo"), ("descripcion", "Descripción"),
            ("categoria", "Categoría"), ("probabilidad", "Probabilidad (1-5)"),
            ("impacto", "Impacto (1-5)"), ("mitigacion", "Mitigación"),
            ("residual", "Riesgo residual (1-25)"),
        ]:
            ent = ctk.CTkEntry(form, placeholder_text=etiqueta, width=280)
            ent.pack(padx=14, pady=5)
            fields[clave] = ent
        tabla_frame = ctk.CTkFrame(visual, fg_color="transparent")
        tabla_frame.pack(fill="both", expand=True, padx=12, pady=12)
        tabla = self._tabla(tabla_frame, [
            ("modulo", "Módulo", 130), ("categoria", "Categoría", 105),
            ("inicial", "Inicial", 75), ("residual", "Residual", 85),
            ("descripcion", "Riesgo", 280),
        ])

        def mostrar_riesgos(riesgos: list[dict[str, Any]]) -> None:
            self._riesgos_cache = riesgos
            tabla.delete(*tabla.get_children())
            for item in self._riesgos_cache:
                tabla.insert("", "end", iid=str(item["_id"]), values=(
                    item.get("modulo", ""), item.get("categoria", ""),
                    item.get("puntaje_inicial", 0), item.get("puntaje_residual", 0),
                    item.get("descripcion", ""),
                ))
            self._dibujar_riesgos(visual, riesgos)
        def refrescar() -> None:
            self._trabajo(self.db.obtener_riesgos, mostrar_riesgos)
        def guardar() -> None:
            try:
                valores = {
                    "modulo": fields["modulo"].get().strip(),
                    "descripcion": fields["descripcion"].get().strip(),
                    "categoria": fields["categoria"].get().strip(),
                    "probabilidad": int(fields["probabilidad"].get()),
                    "impacto": int(fields["impacto"].get()),
                    "mitigacion": fields["mitigacion"].get().strip(),
                    "residual": int(fields["residual"].get()),
                }
                if not all(valores[k] for k in ("modulo", "descripcion", "categoria", "mitigacion")):
                    raise ValueError("Completa los campos de texto.")
            except ValueError as error:
                messagebox.showwarning("Datos inválidos", str(error), parent=self)
                return
            if self._riesgo_seleccionado:
                riesgo_id = self._riesgo_seleccionado
                funcion = lambda: self.db.actualizar_riesgo(
                    riesgo_id, **valores
                )
            else:
                funcion = lambda: self.db.guardar_riesgo(**valores)
            self._trabajo(funcion, lambda _: refrescar())
        def cargar_seleccion(_: Any = None) -> None:
            selection = tabla.selection()
            if not selection:
                return
            self._riesgo_seleccionado = selection[0]
            data = next((x for x in self._riesgos_cache
                         if str(x["_id"]) == self._riesgo_seleccionado), {})
            for key in fields:
                fields[key].delete(0, "end")
            for key in fields:
                value = data.get("puntaje_residual") if key == "residual" else data.get(key, "")
                fields[key].insert(0, str(value))
        def borrar() -> None:
            if not self._riesgo_seleccionado:
                messagebox.showwarning("Selecciona un riesgo", "Elige una fila de la tabla.", parent=self)
                return
            if messagebox.askyesno("Eliminar", "¿Eliminar el riesgo seleccionado?", parent=self):
                riesgo_id = self._riesgo_seleccionado
                self._trabajo(
                    lambda: self.db.eliminar_riesgo(riesgo_id),
                    lambda _: (setattr(self, "_riesgo_seleccionado", None), refrescar()),
                )
        ctk.CTkButton(form, text="Guardar / actualizar riesgo", command=guardar).pack(
            fill="x", padx=14, pady=(10, 5)
        )
        ctk.CTkButton(form, text="Nuevo riesgo", fg_color=PANEL_2,
                      command=lambda: (setattr(self, "_riesgo_seleccionado", None),
                                       [entry.delete(0, "end") for entry in fields.values()])).pack(
                                           fill="x", padx=14, pady=5)
        ctk.CTkButton(form, text="Eliminar seleccionado", fg_color="#622D2D",
                      hover_color="#843737", command=borrar).pack(fill="x", padx=14, pady=5)
        tabla.bind("<<TreeviewSelect>>", cargar_seleccion)
        refrescar()

    def _dibujar_riesgos(self, parent: Any, riesgos: list[dict[str, Any]]) -> None:
        if self._risk_canvas is not None:
            self._risk_canvas.get_tk_widget().destroy()
        if self._risk_summary_label is not None:
            self._risk_summary_label.destroy()
        fig = Figure(figsize=(6, 3.5), dpi=100, facecolor=PANEL)
        ax = fig.add_subplot(111)
        ax.set_facecolor(PANEL)
        if riesgos:
            xs = [item.get("probabilidad", 1) for item in riesgos]
            ys = [item.get("impacto", 1) for item in riesgos]
            sizes = [60 + item.get("puntaje_inicial", 1) * 9 for item in riesgos]
            colors = [item.get("puntaje_inicial", 0) for item in riesgos]
            ax.scatter(xs, ys, s=sizes, c=colors, cmap="RdYlGn_r",
                       edgecolors="white", linewidths=0.6, alpha=0.85)
            for i, item in enumerate(riesgos):
                ax.annotate(item.get("modulo", f"R{i+1}")[:12], (xs[i], ys[i]),
                            xytext=(4, 4), textcoords="offset points",
                            color=TEXTO, fontsize=8)
        ax.set(xlim=(0.5, 5.5), ylim=(0.5, 5.5), xticks=range(1, 6),
               yticks=range(1, 6), xlabel="Probabilidad", ylabel="Impacto",
               title="Riesgo inherente · burbuja = puntaje")
        ax.tick_params(colors=SUAVE)
        ax.xaxis.label.set_color(SUAVE)
        ax.yaxis.label.set_color(SUAVE)
        ax.title.set_color(TEXTO)
        ax.grid(color="#314239", linestyle="--", alpha=0.7)
        fig.tight_layout()
        self._risk_canvas = FigureCanvasTkAgg(fig, master=parent)
        self._risk_canvas.draw()
        self._risk_canvas.get_tk_widget().pack(fill="x", padx=12, pady=(12, 0))
        self._risk_summary_label = ctk.CTkLabel(
            parent,
            text="Puntaje residual guardado por riesgo para visualizar la reducción tras mitigación.",
            text_color=SUAVE, font=("Segoe UI", 10),
        )
        self._risk_summary_label.pack(anchor="w", padx=20, pady=7)

    def _pagina_reportes(self) -> None:
        self._encabezado("Reportes y evaluaciones", "Exporta las colecciones y revisa las respuestas registradas del LLM")
        panel = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        panel.pack(fill="x", padx=30, pady=10)
        tipo = ctk.CTkOptionMenu(panel, values=["JSON", "CSV", "PDF"])
        tipo.pack(side="left", padx=18, pady=18)
        ctk.CTkLabel(panel, text="Incluye camiones, accesos, incidentes, riesgos y evaluaciones",
                     text_color=SUAVE).pack(side="left", padx=8)
        ctk.CTkButton(panel, text="Exportar reporte", command=lambda: self._exportar(tipo.get())).pack(
            side="right", padx=18, pady=18
        )
        ctk.CTkLabel(
            self.contenido,
            text="Los campos de fecha se conservan como ISO 8601. Los identificadores MongoDB se exportan como texto.",
            text_color=SUAVE, font=("Segoe UI", 11),
        ).pack(anchor="w", padx=34, pady=10)
        contenedor = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        contenedor.pack(fill="both", expand=True, padx=30, pady=(0, 24))
        tabla_frame = ctk.CTkFrame(contenedor, fg_color="transparent")
        tabla_frame.pack(fill="both", expand=True, padx=12, pady=12)
        tabla = self._tabla(tabla_frame, [
            ("id", "ID", 105), ("modelo", "Modelo", 120),
            ("latencia", "Latencia (s)", 100), ("coincidio", "Coincidió", 95),
            ("fecha", "Fecha", 155), ("prompt", "Prompt", 360),
        ])
        editor = ctk.CTkTextbox(contenedor, height=95, fg_color="#0B120E", text_color=TEXTO)
        editor.pack(fill="x", padx=12, pady=(0, 6))
        coincidencia = ctk.CTkSwitch(contenedor, text="Respuesta coincidió con reglas")
        coincidencia.pack(anchor="w", padx=14, pady=4)
        cache: dict[str, dict[str, Any]] = {}
        seleccionado: dict[str, str | None] = {"id": None}
        def mostrar_evaluaciones(items: list[dict[str, Any]]) -> None:
            cache.clear()
            tabla.delete(*tabla.get_children())
            for item in items:
                item_id = str(item["_id"])
                cache[item_id] = item
                tabla.insert("", "end", iid=item_id, values=(
                    item_id[-8:], item.get("modelo", ""),
                    item.get("latencia_seg", 0), "Sí" if item.get("coincidio_con_reglas") else "No",
                    str(item.get("fecha", ""))[:19], str(item.get("prompt", ""))[:100],
                ))
        def refrescar_evaluaciones() -> None:
            self._trabajo(self.db.obtener_evaluaciones_llm, mostrar_evaluaciones)
        def seleccionar_evaluacion(_: Any = None) -> None:
            seleccion = tabla.selection()
            if not seleccion:
                return
            seleccionado["id"] = seleccion[0]
            item = cache.get(seleccion[0], {})
            editor.delete("1.0", "end")
            editor.insert("end", json.dumps(item.get("respuesta", {}), ensure_ascii=False, indent=2))
            if item.get("coincidio_con_reglas"):
                coincidencia.select()
            else:
                coincidencia.deselect()
        def guardar_evaluacion() -> None:
            item_id = seleccionado["id"]
            if not item_id:
                messagebox.showwarning("Selecciona una evaluación", "Elige un registro de la tabla.", parent=self)
                return
            try:
                respuesta = json.loads(editor.get("1.0", "end"))
                if not isinstance(respuesta, dict):
                    raise ValueError("La respuesta debe ser un objeto JSON.")
            except (json.JSONDecodeError, ValueError) as error:
                messagebox.showwarning("JSON inválido", str(error), parent=self)
                return
            coincidio = bool(coincidencia.get())
            self._trabajo(
                lambda: self.db.actualizar_evaluacion_llm(item_id, respuesta, coincidio),
                lambda _: refrescar_evaluaciones(),
            )
        def borrar_evaluacion() -> None:
            item_id = seleccionado["id"]
            if not item_id:
                messagebox.showwarning("Selecciona una evaluación", "Elige un registro de la tabla.", parent=self)
                return
            if messagebox.askyesno("Eliminar evaluación", "¿Eliminar este registro?", parent=self):
                self._trabajo(
                    lambda: self.db.eliminar_evaluacion_llm(item_id),
                    lambda _: (seleccionado.update({"id": None}), refrescar_evaluaciones()),
                )
        tabla.bind("<<TreeviewSelect>>", seleccionar_evaluacion)
        acciones = ctk.CTkFrame(contenedor, fg_color="transparent")
        acciones.pack(fill="x", padx=12, pady=(3, 12))
        ctk.CTkButton(acciones, text="Guardar respuesta editada",
                      command=guardar_evaluacion).pack(side="left", padx=(0, 8))
        ctk.CTkButton(acciones, text="Eliminar evaluación", fg_color="#622D2D",
                      hover_color="#843737", command=borrar_evaluacion).pack(side="left")
        refrescar_evaluaciones()

    def _exportar(self, formato: str) -> None:
        extensiones = {"JSON": ".json", "CSV": ".csv", "PDF": ".pdf"}
        ruta = filedialog.asksaveasfilename(
            parent=self, defaultextension=extensiones[formato],
            filetypes=[(f"{formato} files", f"*{extensiones[formato]}")],
        )
        if not ruta:
            return
        def exportar_archivo() -> None:
            datos = {
                "camiones": self.db.listar_camiones(),
                "accesos": self.db.obtener_historial_accesos(10000),
                "incidentes": self.db.obtener_incidentes(10000),
                "riesgos_eticos": self.db.obtener_riesgos(),
                "evaluaciones_llm": self.db.obtener_evaluaciones_llm(10000),
            }
            serializados = {
                nombre: [{k: str(v) if k == "_id" else v for k, v in item.items()}
                         for item in items]
                for nombre, items in datos.items()
            }
            if formato == "JSON":
                with open(ruta, "w", encoding="utf-8") as archivo:
                    json.dump(serializados, archivo, ensure_ascii=False, indent=2, default=str)
            elif formato == "CSV":
                with open(ruta, "w", encoding="utf-8-sig", newline="") as archivo:
                    writer = csv.writer(archivo)
                    writer.writerow(["coleccion", "registro_json"])
                    for nombre, items in serializados.items():
                        for item in items:
                            writer.writerow([nombre, json.dumps(item, ensure_ascii=False, default=str)])
            else:
                with PdfPages(ruta) as pdf:
                    for nombre, items in serializados.items():
                        fig = Figure(figsize=(8.27, 11.69), facecolor="white")
                        ax = fig.add_subplot(111)
                        ax.axis("off")
                        lines = [f"LogiSmart · {nombre}", f"Registros: {len(items)}", ""]
                        for item in items:
                            lines.extend([json.dumps(item, ensure_ascii=False, default=str), ""])
                        for page_start in range(0, len(lines), 42):
                            ax.clear()
                            ax.axis("off")
                            ax.text(0.04, 0.97, "\n".join(lines[page_start:page_start + 42]),
                                    va="top", family="monospace", fontsize=7, wrap=True)
                            pdf.savefig(fig, bbox_inches="tight")
        self._trabajo(
            exportar_archivo,
            lambda _: messagebox.showinfo(
                "Reporte exportado", f"Archivo guardado en:\n{ruta}", parent=self
            ),
            lambda error: messagebox.showerror(
                "Error al exportar", str(error), parent=self
            ),
        )

    def _pagina_configuracion(self) -> None:
        self._encabezado("Configuración", "Conexión MongoDB, servicio local Ollama y modelo")
        panel = ctk.CTkFrame(self.contenido, fg_color=PANEL, corner_radius=14)
        panel.pack(fill="x", padx=30, pady=5)
        campos = [
            ("MONGODB_URI", self.db.uri),
            ("MONGODB_DB", self.db.db_name),
            ("MONGODB_ACCESOS_COLLECTION", self.db.access_collection),
            ("OLLAMA_URL", self.clasificador.ollama_url),
            ("OLLAMA_MODEL", self.clasificador.model_name),
        ]
        widgets: dict[str, Any] = {}
        for i, (nombre, valor) in enumerate(campos):
            ctk.CTkLabel(panel, text=nombre, text_color=SUAVE).grid(
                row=i, column=0, sticky="w", padx=18, pady=11
            )
            entrada = ctk.CTkEntry(panel, width=660, show="*" if nombre == "MONGODB_URI" else "")
            entrada.insert(0, valor)
            entrada.grid(row=i, column=1, sticky="ew", padx=18, pady=8)
            widgets[nombre] = entrada
        panel.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(panel, text="UMBRAL_REVISION", text_color=SUAVE).grid(
            row=5, column=0, sticky="w", padx=18, pady=11
        )
        umbral = ctk.CTkOptionMenu(
            panel, values=["BAJA", "MEDIA", "ALTA", "CRITICA"]
        )
        umbral.set(self.clasificador.umbral_revision)
        umbral.grid(row=5, column=1, sticky="w", padx=18, pady=8)
        simulacion = ctk.CTkSwitch(
            panel, text="Simulación de correo: clasificar solo con reglas locales",
        )
        if self.clasificador.modo_simulacion:
            simulacion.select()
        simulacion.grid(row=6, column=1, sticky="w", padx=18, pady=8)
        estado = ctk.CTkLabel(self.contenido, text="", text_color=SUAVE)
        estado.pack(anchor="w", padx=35, pady=10)

        def conectar() -> None:
            uri = widgets["MONGODB_URI"].get().strip()
            database = widgets["MONGODB_DB"].get().strip()
            access_collection = widgets["MONGODB_ACCESOS_COLLECTION"].get().strip()
            if not uri or not database or not access_collection:
                messagebox.showwarning("Configuración incompleta",
                                       "Ingresa URI, base de datos y colección de accesos.", parent=self)
                return
            def proceso() -> bool:
                self.db.uri = uri
                self.db.db_name = database
                self.db.access_collection = access_collection
                conectado = self.db.conectar()
                if conectado:
                    cargar_datos_demo(self.db)
                return conectado
            def listo(conectado: bool) -> None:
                self._actualizar_estado_db()
                if conectado:
                    estado.configure(text=f"MongoDB conectado: {database}", text_color=VERDE)
                else:
                    estado.configure(
                        text=f"Sin conexión: {self.db.ultimo_error}", text_color=AMBAR
                    )
            self._trabajo(proceso, listo)
        def aplicar_ollama() -> None:
            ollama_url = widgets["OLLAMA_URL"].get().strip()
            model_name = widgets["OLLAMA_MODEL"].get().strip()
            if not ollama_url or not model_name:
                messagebox.showwarning(
                    "Configuración incompleta", "Indica el endpoint y el nombre del modelo.",
                    parent=self,
                )
                return
            self.clasificador.ollama_url = ollama_url
            self.clasificador.model_name = model_name
            self.asistente.ollama_url = self.clasificador.ollama_url
            self.asistente.model_name = self.clasificador.model_name
            self.clasificador.umbral_revision = umbral.get()
            self.clasificador.modo_simulacion = bool(simulacion.get())
            estado.configure(
                text="Configuración aplicada para esta sesión.", text_color=VERDE
            )
        botones = ctk.CTkFrame(self.contenido, fg_color="transparent")
        botones.pack(anchor="w", padx=30, pady=8)
        ctk.CTkButton(botones, text="Probar / conectar MongoDB", command=conectar).pack(
            side="left", padx=5
        )
        ctk.CTkButton(botones, text="Aplicar configuración",
                      fg_color=VERDE_OSCURO, command=aplicar_ollama).pack(side="left", padx=5)
        ctk.CTkLabel(
            self.contenido,
            text="Usa variables de entorno MONGODB_URI, MONGODB_DB, OLLAMA_URL y OLLAMA_MODEL para persistir configuración sin guardar claves en el código.",
            text_color=SUAVE, wraplength=870, justify="left",
        ).pack(anchor="w", padx=34, pady=12)

    def abrir_tutor(self) -> None:
        ruta = os.path.join(os.path.dirname(__file__), "p02primertutor_llm.py")
        try:
            subprocess.Popen([sys.executable, ruta], cwd=os.path.dirname(__file__))
        except OSError as error:
            messagebox.showerror("No se pudo abrir el tutor", str(error), parent=self)

    def _cerrar(self) -> None:
        self.db.cerrar()
        self.destroy()


if __name__ == "__main__":
    LogiSmartApp().mainloop()
