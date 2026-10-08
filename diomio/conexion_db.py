"""Persistencia MongoDB de LogiSmart."""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from pymongo import MongoClient


class MongoDBManager:
    """Acceso a las colecciones del sistema y validación explícita de conexión."""

    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
        access_collection: str | None = None,
        timeout_ms: int = 2500,
    ) -> None:
        self.uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.db_name = db_name or os.getenv("MONGODB_DB", "logismart_db")
        self.access_collection = (
            access_collection or os.getenv("MONGODB_ACCESOS_COLLECTION", "accesos")
        )
        self.client: MongoClient | None = None
        self.db: Any = None
        self.ultimo_error: str | None = None
        self.conectar(timeout_ms)

    def conectar(self, timeout_ms: int = 2500) -> bool:
        if self.client is not None:
            self.client.close()
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
            )
            self.client.admin.command("ping")
            self.db = self.client[self.db_name]
            self.ultimo_error = None
            return True
        except Exception as error:
            self.db = None
            self.ultimo_error = str(error)
            if self.client is not None:
                self.client.close()
            self.client = None
            return False

    def esta_conectado(self) -> bool:
        return self.db is not None

    def _coleccion(self, nombre: str) -> Any:
        if not self.esta_conectado():
            raise ConnectionError(
                f"MongoDB no está disponible. Revisa MONGODB_URI y el servicio. "
                f"Detalle: {self.ultimo_error or 'sin conexión'}"
            )
        if nombre == "accesos":
            nombre = self.access_collection
        return self.db[nombre]

    @staticmethod
    def _id(valor: Any) -> ObjectId:
        if isinstance(valor, ObjectId):
            return valor
        try:
            return ObjectId(str(valor))
        except Exception as error:
            raise ValueError("El identificador seleccionado no es válido.") from error

    @staticmethod
    def _ahora() -> datetime:
        return datetime.now(timezone.utc)

    # Camiones
    def registrar_camion(
        self,
        camion_id: str,
        placa: str,
        empresa: str,
        autorizacion: bool = True,
        cert_conductor: bool = True,
    ) -> Any:
        doc = {
            "camion_id": camion_id.strip().upper(),
            "placa": placa.strip().upper(),
            "empresa": empresa.strip(),
            "autorizacion": bool(autorizacion),
            "cert_conductor": bool(cert_conductor),
            "fecha_registro": self._ahora(),
        }
        return self._coleccion("camiones").update_one(
            {"camion_id": doc["camion_id"]}, {"$set": doc}, upsert=True
        )

    def obtener_camion(self, identificador: str) -> dict[str, Any] | None:
        clave = identificador.strip().upper()
        return self._coleccion("camiones").find_one(
            {"$or": [{"camion_id": clave}, {"placa": clave}]}
        )

    def listar_camiones(self) -> list[dict[str, Any]]:
        return list(self._coleccion("camiones").find().sort("camion_id", 1))

    def contar_camiones(self) -> int:
        return self._coleccion("camiones").count_documents({})

    def actualizar_camion(
        self,
        id_anterior: str,
        camion_id: str,
        placa: str,
        empresa: str,
        autorizacion: bool,
        cert_conductor: bool,
    ) -> bool:
        doc = {
            "camion_id": camion_id.strip().upper(),
            "placa": placa.strip().upper(),
            "empresa": empresa.strip(),
            "autorizacion": bool(autorizacion),
            "cert_conductor": bool(cert_conductor),
        }
        result = self._coleccion("camiones").update_one(
            {"camion_id": id_anterior.strip().upper()}, {"$set": doc}
        )
        return result.matched_count > 0

    def eliminar_camion(self, identificador: str) -> bool:
        result = self._coleccion("camiones").delete_one({"camion_id": identificador})
        return result.deleted_count > 0

    # Accesos
    def registrar_acceso(
        self,
        camion_id: str,
        P: bool,
        Q: bool,
        R: bool,
        S: bool,
        res_A: bool,
        res_E: bool,
        explicacion: str,
        operador: str = "Operador",
        C: bool = True,
        M: bool = False,
        H: bool = False,
    ) -> Any:
        return self._coleccion("accesos").insert_one(
            {
                "camion_id": camion_id.strip().upper(),
                "premisas": {
                    "P": P, "Q": Q, "R": R, "S": S,
                    "C": C, "M": M, "H": H,
                },
                "resultados": {"A": res_A, "E": res_E},
                "explicacion": explicacion,
                "marca_tiempo": self._ahora(),
                "operador": operador.strip() or "Operador",
            }
        )

    def obtener_historial_accesos(self, limite: int = 100) -> list[dict[str, Any]]:
        return list(
            self._coleccion("accesos")
            .find()
            .sort("marca_tiempo", -1)
            .limit(max(1, limite))
        )

    def actualizar_acceso(
        self,
        id_acceso: Any,
        operador: str | None = None,
        explicacion: str | None = None,
    ) -> bool:
        cambios: dict[str, Any] = {}
        if operador is not None:
            cambios["operador"] = operador.strip() or "Operador"
        if explicacion is not None:
            cambios["explicacion"] = explicacion.strip()
        if not cambios:
            raise ValueError("Indica al menos un campo para actualizar.")
        result = self._coleccion("accesos").update_one(
            {"_id": self._id(id_acceso)}, {"$set": cambios}
        )
        return result.matched_count > 0

    def eliminar_acceso(self, id_acceso: Any) -> bool:
        return self._coleccion("accesos").delete_one(
            {"_id": self._id(id_acceso)}
        ).deleted_count > 0

    # Incidentes
    def guardar_incidente(
        self,
        correo_original: str,
        clasificacion: dict[str, Any],
        datos_extraidos: list[str] | dict[str, Any],
        estado: str = "nuevo",
    ) -> Any:
        ahora = self._ahora()
        return self._coleccion("incidentes").insert_one(
            {
                "correo_original": correo_original,
                "clasificacion": clasificacion,
                "datos_extraidos": datos_extraidos,
                "estado": estado,
                "fecha_recepcion": ahora,
                "historial": [{"estado": estado, "fecha": ahora}],
            }
        )

    def obtener_incidentes(self, limite: int = 500) -> list[dict[str, Any]]:
        return list(
            self._coleccion("incidentes")
            .find()
            .sort("fecha_recepcion", -1)
            .limit(max(1, limite))
        )

    def actualizar_incidente(
        self,
        id_incidente: Any,
        clasificacion: dict[str, Any] | None = None,
        nuevo_estado: str | None = None,
    ) -> bool:
        cambios: dict[str, Any] = {"actualizado_en": self._ahora()}
        if clasificacion is not None:
            cambios["clasificacion"] = clasificacion
        if nuevo_estado is not None:
            if nuevo_estado not in {"nuevo", "en_atencion", "cerrado"}:
                raise ValueError("Estado de incidente no permitido.")
            cambios["estado"] = nuevo_estado
            cambios["historial"] = {
                "$each": [{"estado": nuevo_estado, "fecha": self._ahora()}]
            }
            result = self._coleccion("incidentes").update_one(
                {"_id": self._id(id_incidente)},
                {"$set": {k: v for k, v in cambios.items() if k != "historial"},
                 "$push": {"historial": cambios["historial"]}},
            )
        else:
            result = self._coleccion("incidentes").update_one(
                {"_id": self._id(id_incidente)}, {"$set": cambios}
            )
        return result.matched_count > 0

    def actualizar_estado_incidente(self, id_incidente: Any, nuevo_estado: str) -> bool:
        return self.actualizar_incidente(id_incidente, nuevo_estado=nuevo_estado)

    def eliminar_incidente(self, id_incidente: Any) -> bool:
        return self._coleccion("incidentes").delete_one(
            {"_id": self._id(id_incidente)}
        ).deleted_count > 0

    def agregacion_incidentes_semana(
        self,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> list[dict[str, Any]]:
        pipeline: list[dict[str, Any]] = []
        rango_fecha: dict[str, datetime] = {}
        if desde is not None:
            rango_fecha["$gte"] = desde
        if hasta is not None:
            rango_fecha["$lt"] = hasta + timedelta(days=1)
        if rango_fecha:
            pipeline.append({"$match": {"fecha_recepcion": rango_fecha}})
        pipeline.extend([
            {
                "$group": {
                    "_id": {
                        "categoria": "$clasificacion.categoria",
                        "anio": {"$isoWeekYear": "$fecha_recepcion"},
                        "semana": {"$isoWeek": "$fecha_recepcion"},
                    },
                    "total": {"$sum": 1},
                }
            },
            {"$sort": {"_id.anio": -1, "_id.semana": -1, "_id.categoria": 1}},
        ])
        return list(self._coleccion("incidentes").aggregate(pipeline))

    # Riesgos éticos
    def guardar_riesgo(
        self,
        modulo: str,
        descripcion: str,
        categoria: str,
        probabilidad: int,
        impacto: int,
        mitigacion: str,
        residual: int,
    ) -> Any:
        if not (1 <= probabilidad <= 5 and 1 <= impacto <= 5 and 1 <= residual <= 25):
            raise ValueError("Probabilidad e impacto deben ser 1-5 y residual 1-25.")
        ahora = self._ahora()
        doc = {
            "modulo": modulo.strip(),
            "descripcion": descripcion.strip(),
            "categoria": categoria.strip(),
            "probabilidad": probabilidad,
            "impacto": impacto,
            "puntaje_inicial": probabilidad * impacto,
            "mitigacion": mitigacion.strip(),
            "puntaje_residual": residual,
            "fecha": ahora,
            "historico": [{"fecha": ahora, "puntaje_inicial": probabilidad * impacto,
                           "puntaje_residual": residual}],
        }
        return self._coleccion("riesgos_eticos").insert_one(doc)

    def obtener_riesgos(self) -> list[dict[str, Any]]:
        return list(self._coleccion("riesgos_eticos").find().sort("puntaje_inicial", -1))

    def actualizar_riesgo(
        self,
        id_riesgo: Any,
        modulo: str,
        descripcion: str,
        categoria: str,
        probabilidad: int,
        impacto: int,
        mitigacion: str,
        residual: int,
    ) -> bool:
        if not (1 <= probabilidad <= 5 and 1 <= impacto <= 5 and 1 <= residual <= 25):
            raise ValueError("Probabilidad e impacto deben ser 1-5 y residual 1-25.")
        puntaje = probabilidad * impacto
        ahora = self._ahora()
        result = self._coleccion("riesgos_eticos").update_one(
            {"_id": self._id(id_riesgo)},
            {
                "$set": {
                    "modulo": modulo.strip(), "descripcion": descripcion.strip(),
                    "categoria": categoria.strip(), "probabilidad": probabilidad,
                    "impacto": impacto, "puntaje_inicial": puntaje,
                    "mitigacion": mitigacion.strip(), "puntaje_residual": residual,
                    "fecha": ahora,
                },
                "$push": {"historico": {
                    "fecha": ahora, "puntaje_inicial": puntaje,
                    "puntaje_residual": residual,
                }},
            },
        )
        return result.matched_count > 0

    def eliminar_riesgo(self, id_riesgo: Any) -> bool:
        return self._coleccion("riesgos_eticos").delete_one(
            {"_id": self._id(id_riesgo)}
        ).deleted_count > 0

    # Evaluaciones del LLM
    def registrar_evaluacion_llm(
        self,
        prompt: str,
        respuesta: dict[str, Any],
        modelo: str,
        latencia: float,
        coincidio_con_reglas: bool,
    ) -> Any:
        return self._coleccion("evaluaciones_llm").insert_one(
            {
                "prompt": prompt, "respuesta": respuesta, "modelo": modelo,
                "latencia_seg": latencia,
                "coincidio_con_reglas": coincidio_con_reglas,
                "fecha": self._ahora(),
            }
        )

    def obtener_evaluaciones_llm(self, limite: int = 500) -> list[dict[str, Any]]:
        return list(
            self._coleccion("evaluaciones_llm")
            .find()
            .sort("fecha", -1)
            .limit(max(1, limite))
        )

    def actualizar_evaluacion_llm(
        self,
        id_evaluacion: Any,
        respuesta: dict[str, Any],
        coincidio_con_reglas: bool,
    ) -> bool:
        result = self._coleccion("evaluaciones_llm").update_one(
            {"_id": self._id(id_evaluacion)},
            {"$set": {
                "respuesta": respuesta,
                "coincidio_con_reglas": bool(coincidio_con_reglas),
                "revisada_en": self._ahora(),
            }},
        )
        return result.matched_count > 0

    def eliminar_evaluacion_llm(self, id_evaluacion: Any) -> bool:
        return self._coleccion("evaluaciones_llm").delete_one(
            {"_id": self._id(id_evaluacion)}
        ).deleted_count > 0

    def buscar_registros_asistente(self, consulta: str) -> list[dict[str, Any]]:
        clave = consulta.strip()
        if not clave:
            return []
        patron = {"$regex": re.escape(clave), "$options": "i"}
        camiones = list(
            self._coleccion("camiones").find(
                {"$or": [{"camion_id": patron}, {"placa": patron}]}
            ).limit(5)
        )
        ids = [c.get("camion_id") for c in camiones] + [c.get("placa") for c in camiones]
        query: dict[str, Any] = {"$or": [
            {"correo_original": patron},
            {"clasificacion.resumen": patron},
            {"datos_extraidos": patron},
        ]}
        if ids:
            query["$or"].extend([
                {"datos_extraidos": {"$in": ids}},
                {"camion_id": {"$in": ids}},
            ])
        incidentes = list(
            self._coleccion("incidentes").find(query).sort("fecha_recepcion", -1).limit(10)
        )
        accesos = list(
            self._coleccion("accesos").find({"camion_id": {"$regex": re.escape(clave),
                                                              "$options": "i"}})
            .sort("marca_tiempo", -1).limit(10)
        )
        return [
            *({"coleccion": "camiones", **item} for item in camiones),
            *({"coleccion": "incidentes", **item} for item in incidentes),
            *({"coleccion": "accesos", **item} for item in accesos),
        ]

    def cerrar(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None


def cargar_datos_demo(db_manager: MongoDBManager) -> None:
    """Carga ejemplos mínimos de forma idempotente; no altera bases pobladas."""
    if not db_manager.esta_conectado():
        return
    if db_manager.db.camiones.count_documents({}) == 0:
        db_manager.registrar_camion("CAM-101", "ABC-123", "LogiExpress", True, True)
        db_manager.registrar_camion("CAM-102", "XYZ-789", "TransMetepec", True, False)
        db_manager.registrar_camion("CAM-103", "MNO-456", "CargaSegura", False, True)
    if db_manager._coleccion("accesos").count_documents({}) == 0:
        db_manager.registrar_acceso(
            "CAM-102", True, False, False, True, False, True,
            "Acceso normal denegado: certificación vencida. "
            "La regla R3 bloquea A y solicita inspección especial.",
            operador="Demo", C=False, M=False, H=False,
        )
    if db_manager.db.incidentes.count_documents({}) == 0:
        correo = (
            "La unidad CAM-102 se presentó con la certificación del conductor vencida; "
            "favor de enviarla a inspección antes de continuar."
        )
        db_manager.guardar_incidente(
            correo,
            {
                "categoria": "Documentación", "prioridad": "ALTA",
                "entidades": ["CAM-102"],
                "resumen": "Certificación del conductor vencida; requiere inspección.",
                "requiere_revision_humana": True, "origen": "Demostración",
            },
            ["CAM-102"],
        )
    if db_manager.db.riesgos_eticos.count_documents({}) == 0:
        db_manager.guardar_riesgo(
            "Clasificador", "Alucinación al extraer datos del correo", "Técnico",
            4, 4, "Validación Pydantic, reintento y respaldo por reglas", 2,
        )
        db_manager.guardar_riesgo(
            "Entrada textual", "Sesgo ante ortografía informal", "Social",
            3, 3, "Pruebas con variaciones ortográficas y revisión humana", 2,
        )
        db_manager.guardar_riesgo(
            "Operación", "Dependencia excesiva de decisiones automáticas", "Operativo",
            4, 5, "Revisión humana en discrepancias y decisiones críticas", 2,
        )
        db_manager.guardar_riesgo(
            "Privacidad", "Exposición de datos personales del conductor", "Legal",
            2, 5, "Minimizar datos y restringir accesos", 1,
        )
        db_manager.guardar_riesgo(
            "Asistente LLM", "Respuesta alucinada o no sustentada", "Técnico",
            3, 5, "Responder únicamente con contexto recuperado y citar fuente", 2,
        )
