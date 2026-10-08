"""Clasificador híbrido de incidentes con validación y respaldo local."""

import re
import time
import unicodedata
from collections import defaultdict
from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class EsquemaIncidente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categoria: Literal["Mecánico", "Documentación", "Seguridad", "Retraso", "Otro"]
    prioridad: Literal["BAJA", "MEDIA", "ALTA", "CRITICA"]
    entidades: list[str] = Field(default_factory=list)
    resumen: str = Field(min_length=1, max_length=400)


DATASET_30 = [
    ("El camión CAM-101 tuvo una fuga de aceite grave en la autopista.", "Mecánico", "ALTA"),
    ("Unidad XYZ-789 detenida por la policía por licencia vencida del chofer.", "Documentación", "ALTA"),
    ("Llegaremos 20 minutos tarde a la bodega por tráfico ligero.", "Retraso", "BAJA"),
    ("El sello de seguridad del contenedor ABC-123 viene roto.", "Seguridad", "ALTA"),
    ("Falla eléctrica en el tablero del camión CAM-102.", "Mecánico", "MEDIA"),
    ("Chofer no trae la certificación de materiales peligrosos.", "Documentación", "ALTA"),
    ("Retraso de 3 horas por cierre de caseta de cobro.", "Retraso", "MEDIA"),
    ("Reporte de intento de asalto en la ruta norte a la unidad MNO-456.", "Seguridad", "ALTA"),
    ("Cambio de llanta ponchada en estación de servicio.", "Mecánico", "BAJA"),
    ("Falta firma en la carta porte del embarque 554.", "Documentación", "MEDIA"),
    ("Calentamiento de motor en unidad CAM-103.", "Mecánico", "MEDIA"),
    ("Monitoreo indica parada no autorizada en zona de riesgo.", "Seguridad", "ALTA"),
    ("Clima lluvioso causa demora de 45 min.", "Retraso", "BAJA"),
    ("Sello de seguridad no coincide con el manifiesto.", "Seguridad", "ALTA"),
    ("Se perdió el permiso de tránsito estatal.", "Documentación", "MEDIA"),
    ("Frenos respondiendo lento en bajada de montaña.", "Mecánico", "ALTA"),
    ("Chofer reporta malestar físico y detiene la unidad.", "Otro", "MEDIA"),
    ("Serranía bloqueada por derrumbe, desviando ruta.", "Retraso", "MEDIA"),
    ("Comportamiento sospechoso de vehículo escolta.", "Seguridad", "ALTA"),
    ("Revisión de rutina en báscula SCT aprobada con demora.", "Retraso", "BAJA"),
    ("Luces traseras apagadas en la unidad XYZ-100.", "Mecánico", "BAJA"),
    ("Extravío de tarjeta de circulación.", "Documentación", "MEDIA"),
    ("Falla en el sistema GPS de rastreo satelital.", "Mecánico", "MEDIA"),
    ("Reporte de mercancía mojada dentro de la caja.", "Otro", "MEDIA"),
    ("Protesta en la avenida principal impide el paso.", "Retraso", "MEDIA"),
    ("Caja refrigerada perdió temperatura objetivo.", "Mecánico", "ALTA"),
    ("Inconsistencia en la identificación oficial del operador.", "Documentación", "ALTA"),
    ("Intento de apertura forzada de la puerta trasera.", "Seguridad", "ALTA"),
    ("Llegada anticipada a la planta de entrega.", "Retraso", "BAJA"),
    ("Mantenimiento preventivo agendado para mañana.", "Otro", "BAJA"),
]

_ORDEN_PRIORIDAD = {"BAJA": 1, "MEDIA": 2, "ALTA": 3, "CRITICA": 4}


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_acentos if not unicodedata.combining(c))


class ClasificadorHibrido:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434/api/generate",
        model_name: str = "llama3.2",
        timeout: float = 20,
        reintentos: int = 2,
    ) -> None:
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.timeout = timeout
        self.reintentos = max(1, reintentos)
        self.modo_simulacion = False
        self.umbral_revision = "ALTA"

    def clasificar_por_reglas(self, texto_correo: str) -> dict[str, Any]:
        texto = _normalizar(texto_correo)
        categorias = [
            ("Documentación", ("documento", "licencia", "permiso", "papeles",
                               "vencido", "carta porte", "certificacion", "identificacion",
                               "tarjeta de circulacion")),
            ("Seguridad", ("asalto", "robo", "policia", "sello", "seguridad",
                           "sospechoso", "apertura forzada", "zona de riesgo",
                           "parada no autorizada")),
            ("Mecánico", ("mecan", "falla", "motor", "llanta", "freno", "fuga",
                          "gps", "luces", "temperatura")),
            ("Retraso", ("tarde", "demora", "retraso", "trafico", "derrumbe",
                         "protesta", "llegada anticipada", "llegaremos")),
        ]
        categoria = next(
            (nombre for nombre, claves in categorias if any(k in texto for k in claves)),
            "Otro",
        )

        urgentes = (
            "urgente", "accidente", "grave", "fuga", "asalto", "roto",
            "detenida por la policia", "intento de apertura", "frenos",
            "no trae la certificacion", "parada no autorizada", "no coincide",
            "sospechoso", "perdio temperatura", "inconsistencia",
        )
        moderados = (
            "retraso de 3 horas", "licencia vencida", "falla electrica",
            "calentamiento", "riesgo", "falta firma", "extrav", "gps",
            "mercancia mojada", "protesta", "malestar", "derrumbe", "permiso",
        )
        if any(k in texto for k in urgentes):
            prioridad = "ALTA"
        elif any(k in texto for k in moderados):
            prioridad = "MEDIA"
        else:
            prioridad = "BAJA"
        entidades = list(dict.fromkeys(
            item.upper() for item in re.findall(
                r"\b(?:CAM-\d{3}|[A-Z]{3}-\d{3})\b", texto_correo, re.IGNORECASE
            )
        ))
        return {
            "categoria": categoria,
            "prioridad": prioridad,
            "entidades": entidades,
            "resumen": texto_correo.strip()[:397] + ("..." if len(texto_correo.strip()) > 397 else ""),
        }

    def clasificar_con_llm(self, texto_correo: str) -> tuple[EsquemaIncidente | None, float]:
        prompt = (
            "Clasifica el correo de incidente de logística. Responde solo JSON, "
            "sin texto adicional. Categoría: Mecánico, Documentación, Seguridad, "
            "Retraso u Otro. Prioridad: BAJA, MEDIA, ALTA o CRITICA. "
            "Campos exactos: categoria, prioridad, entidades (lista de texto), "
            "resumen (una oración). No inventes entidades.\nCorreo:\n"
            + texto_correo
        )
        inicio = time.perf_counter()
        for _ in range(self.reintentos):
            try:
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "format": EsquemaIncidente.model_json_schema(),
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                raw = response.json().get("response", "")
                result = EsquemaIncidente.model_validate_json(raw)
                return result, time.perf_counter() - inicio
            except (requests.RequestException, ValueError, ValidationError, KeyError, TypeError):
                continue
        return None, time.perf_counter() - inicio

    @staticmethod
    def fusionar(
        reglas: dict[str, Any], llm: EsquemaIncidente | None, latencia: float
    ) -> dict[str, Any]:
        resultado_reglas = dict(reglas)
        if llm is None:
            return {
                **resultado_reglas, "latencia": round(latencia, 3),
                "origen": "Respaldo por reglas (Ollama no disponible o JSON inválido)",
                "requiere_revision_humana": True,
            }
        resultado_llm = llm.model_dump()
        discrepancia = (
            resultado_llm["categoria"] != reglas["categoria"]
            or resultado_llm["prioridad"] != reglas["prioridad"]
        )
        if _ORDEN_PRIORIDAD[reglas["prioridad"]] > _ORDEN_PRIORIDAD[resultado_llm["prioridad"]]:
            resultado_llm["prioridad"] = reglas["prioridad"]
        if discrepancia:
            resultado_llm["requiere_revision_humana"] = True
            resultado_llm["origen"] = "Híbrido (discrepancia; prioridad más alta)"
        else:
            resultado_llm["requiere_revision_humana"] = False
            resultado_llm["origen"] = "Híbrido (coincidencia)"
        resultado_llm["latencia"] = round(latencia, 3)
        resultado_llm["clasificacion_reglas"] = resultado_reglas
        return resultado_llm

    def procesar_incidente(self, texto_correo: str) -> dict[str, Any]:
        if not texto_correo.strip():
            raise ValueError("El correo no puede estar vacío.")
        reglas = self.clasificar_por_reglas(texto_correo)
        if self.modo_simulacion:
            resultado = {
                **reglas,
                "latencia": 0.0,
                "origen": "Simulación local (solo reglas; sin llamada a Ollama)",
                "requiere_revision_humana": False,
            }
        else:
            llm, latencia = self.clasificar_con_llm(texto_correo)
            resultado = self.fusionar(reglas, llm, latencia)
        if _ORDEN_PRIORIDAD[resultado["prioridad"]] >= _ORDEN_PRIORIDAD[self.umbral_revision]:
            resultado["requiere_revision_humana"] = True
            resultado["revision_por_umbral"] = self.umbral_revision
        return resultado

    @staticmethod
    def _metricas(
        predicciones: list[dict[str, Any]],
        categoria_real: list[str],
        prioridad_real: list[str],
    ) -> dict[str, Any]:
        aciertos = sum(
            pred.get("categoria") == real
            for pred, real in zip(predicciones, categoria_real)
        )
        aciertos_prioridad = sum(
            pred.get("prioridad") == real
            for pred, real in zip(predicciones, prioridad_real)
        )
        matriz: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for pred, real in zip(predicciones, categoria_real):
            matriz[real][str(pred.get("categoria", "Sin predicción"))] += 1
        latencias = [float(item.get("latencia", 0)) for item in predicciones]
        hay_predicciones = any(
            pred.get("categoria") != "Sin predicción" for pred in predicciones
        )
        return {
            "exactitud": (
                aciertos / len(categoria_real) if categoria_real and hay_predicciones else None
            ),
            "exactitud_categoria": (
                aciertos / len(categoria_real) if categoria_real and hay_predicciones else None
            ),
            "exactitud_prioridad": (
                aciertos_prioridad / len(prioridad_real)
                if prioridad_real and hay_predicciones else None
            ),
            "matriz_confusion": {k: dict(v) for k, v in matriz.items()},
            "latencia_promedio_seg": (
                sum(latencias) / len(latencias) if latencias and hay_predicciones else None
            ),
        }

    def ejecutar_experimento_30_correos(self) -> dict[str, Any]:
        """Compara reglas, LLM y fusión sobre el conjunto etiquetado de 30 correos."""
        llm_disponible = False
        try:
            base = self.ollama_url.split("/api/", 1)[0].rstrip("/")
            response = requests.get(f"{base}/api/tags", timeout=2)
            response.raise_for_status()
            modelos = response.json().get("models", [])
            esperado = self.model_name.split(":")[0]
            llm_disponible = any(
                str(modelo.get("name", "")).split(":")[0] == esperado
                for modelo in modelos
            )
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
            llm_disponible = False

        resultados = []
        categorias_reales = []
        prioridades_reales = []
        reglas_preds = []
        llm_preds = []
        hibrido_preds = []
        for idx, (texto, categoria, prioridad) in enumerate(DATASET_30, 1):
            regla = self.clasificar_por_reglas(texto)
            llm, latencia = (
                self.clasificar_con_llm(texto) if llm_disponible else (None, 0.0)
            )
            hibrido = self.fusionar(regla, llm, latencia)
            llm_dict = llm.model_dump() if llm else {
                "categoria": "Sin predicción", "prioridad": "Sin predicción",
            }
            llm_dict["latencia"] = latencia
            regla["latencia"] = 0.0
            resultados.append({
                "id": idx, "correo": texto,
                "categoria_real": categoria, "prioridad_real": prioridad,
                "reglas": regla, "llm": llm_dict, "hibrido": hibrido,
            })
            categorias_reales.append(categoria)
            prioridades_reales.append(prioridad)
            reglas_preds.append(regla)
            llm_preds.append(llm_dict)
            hibrido_preds.append(hibrido)
        return {
            "muestras": len(resultados),
            "llm_disponible": llm_disponible,
            "resultados": resultados,
            "metricas": {
                "reglas": self._metricas(reglas_preds, categorias_reales, prioridades_reales),
                "llm": self._metricas(llm_preds, categorias_reales, prioridades_reales),
                "hibrido": self._metricas(hibrido_preds, categorias_reales, prioridades_reales),
            },
        }
