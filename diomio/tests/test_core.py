import unittest
from unittest.mock import patch

import requests

from asistente_rag import AsistenteRAGLogiSmart
from clasificador_hibrido import ClasificadorHibrido, EsquemaIncidente
from conexion_db import MongoDBManager
from motor_reglas import MotorReglasLogistics


class ReglaTests(unittest.TestCase):
    def setUp(self):
        self.motor = MotorReglasLogistics()

    def test_tabla_base_cubre_las_16_combinaciones(self):
        tabla = self.motor.generar_tabla_verdad()
        self.assertEqual(len(tabla), 16)
        self.assertEqual(
            {value for row in tabla for value in row.values()},
            {"V", "F"},
        )
        for row in tabla:
            P, Q, R, S = (row[key] == "V" for key in ("P", "Q", "R", "S"))
            self.assertEqual(row["A"], "V" if P and S and not Q else "F")
            self.assertEqual(row["E"], "V" if P and (R or Q) else "F")

    def test_certificacion_vencida_bloquea_y_envia_a_inspeccion(self):
        result = self.motor.evaluar_acceso(True, False, False, True, C=False)
        self.assertFalse(result["A"])
        self.assertTrue(result["E"])
        self.assertIn("certificación vencida", result["explicacion"])

    def test_material_peligroso_fuera_de_horario_bloquea(self):
        result = self.motor.evaluar_acceso(
            True, False, False, True, M=True, H=True
        )
        self.assertFalse(result["A"])
        self.assertTrue(result["E"])


class ClasificadorTests(unittest.TestCase):
    def test_reglas_reconocen_categorias_y_entidades(self):
        resultado = ClasificadorHibrido().clasificar_por_reglas(
            "Falla grave en CAM-102, fuga de aceite"
        )
        self.assertEqual(resultado["categoria"], "Mecánico")
        self.assertEqual(resultado["prioridad"], "ALTA")
        self.assertEqual(resultado["entidades"], ["CAM-102"])

    def test_llm_invalido_reintenta_y_fusiona_respaldo(self):
        motor = ClasificadorHibrido(reintentos=2)
        with patch("clasificador_hibrido.requests.post",
                   side_effect=requests.ConnectionError("offline")) as llamada:
            resultado = motor.procesar_incidente("Sello de seguridad roto en ABC-123")
        self.assertEqual(llamada.call_count, 2)
        self.assertEqual(resultado["categoria"], "Seguridad")
        self.assertEqual(resultado["prioridad"], "ALTA")
        self.assertTrue(resultado["requiere_revision_humana"])
        self.assertIn("Respaldo", resultado["origen"])

    def test_esquema_rechaza_campos_extra_y_categoria_invalida(self):
        with self.assertRaises(ValueError):
            EsquemaIncidente(
                categoria="Inventada", prioridad="BAJA", entidades=[], resumen="Test"
            )

    def test_fusion_elige_prioridad_mas_alta_y_pide_revision(self):
        motor = ClasificadorHibrido()
        reglas = {
            "categoria": "Seguridad", "prioridad": "ALTA",
            "entidades": [], "resumen": "Alerta de seguridad",
        }
        llm = EsquemaIncidente(
            categoria="Otro", prioridad="BAJA", entidades=[], resumen="Aviso general"
        )
        resultado = motor.fusionar(reglas, llm, 0.2)
        self.assertEqual(resultado["prioridad"], "ALTA")
        self.assertTrue(resultado["requiere_revision_humana"])
        self.assertIn("discrepancia", resultado["origen"])


class RobustezTests(unittest.TestCase):
    def test_db_desconectada_informa_error(self):
        manager = object.__new__(MongoDBManager)
        manager.db = None
        manager.ultimo_error = "offline"
        with self.assertRaisesRegex(ConnectionError, "offline"):
            manager.listar_camiones()

    def test_coleccion_accesos_configurable(self):
        class FakeDatabase:
            def __getitem__(self, name):
                return name

        manager = object.__new__(MongoDBManager)
        manager.db = FakeDatabase()
        manager.access_collection = "actividad"
        self.assertEqual(manager._coleccion("accesos"), "actividad")
        self.assertEqual(manager._coleccion("incidentes"), "incidentes")

    def test_rag_sin_registros_no_llama_al_llm(self):
        class DBVacia:
            def buscar_registros_asistente(self, _consulta):
                _ = _consulta
                return []

        asistente = AsistenteRAGLogiSmart(DBVacia())
        with patch("asistente_rag.requests.post") as llamada:
            respuesta = asistente.responder_consulta("¿Qué pasó con CAM-101?")
        llamada.assert_not_called()
        self.assertIn("No tengo información", respuesta["respuesta"])
        self.assertEqual(respuesta["fuentes"], [])

    def test_rag_responde_conteo_de_camiones_desde_mongodb(self):
        class DBConCamiones:
            def contar_camiones(self):
                return 3

        asistente = AsistenteRAGLogiSmart(DBConCamiones())
        with patch("asistente_rag.requests.post") as llamada:
            respuesta = asistente.responder_consulta(
                "¿Cuántos camiones tengo registrados?"
            )
        llamada.assert_not_called()
        self.assertEqual(
            respuesta["respuesta"],
            "Hay 3 camiones registrados en MongoDB.",
        )
        self.assertEqual(
            respuesta["fuentes"],
            ["MongoDB.camiones / conteo total"],
        )

    def test_rag_lista_camiones_sin_necesitar_ollama(self):
        class DBConCamiones:
            def listar_camiones(self):
                return [
                    {
                        "_id": "mongo-1",
                        "camion_id": "CAM-102",
                        "placa": "XYZ-789",
                        "empresa": "TransMetepec",
                        "autorizacion": True,
                        "cert_conductor": False,
                    }
                ]

        asistente = AsistenteRAGLogiSmart(DBConCamiones())
        with patch("asistente_rag.requests.post") as llamada:
            respuesta = asistente.responder_consulta(
                "Dame detalles de los camiones registrados"
            )
        llamada.assert_not_called()
        self.assertIn("Camiones registrados (1)", respuesta["respuesta"])
        self.assertIn("CAM-102", respuesta["respuesta"])
        self.assertIn("XYZ-789", respuesta["respuesta"])
        self.assertIn("certificación: no vigente", respuesta["respuesta"])
        self.assertEqual(
            respuesta["fuentes"],
            ["MongoDB.camiones / registro mongo-1"],
        )

    def test_rag_muestra_registros_si_ollama_agota_tiempo(self):
        class DBConRegistros:
            def buscar_registros_asistente(self, _consulta):
                _ = _consulta
                return [{
                    "_id": "mongo-2",
                    "coleccion": "incidentes",
                    "correo_original": "Certificación vencida para CAM-102",
                }]

        asistente = AsistenteRAGLogiSmart(DBConRegistros())
        with patch(
            "asistente_rag.requests.post",
            side_effect=requests.ReadTimeout("timeout"),
        ):
            respuesta = asistente.responder_consulta(
                "¿Qué incidente tiene CAM-102?"
            )
        self.assertIn("MongoDB sí recuperó estos registros", respuesta["respuesta"])
        self.assertIn("Certificación vencida", respuesta["respuesta"])
        self.assertEqual(
            respuesta["fuentes"],
            ["MongoDB.incidentes / registro mongo-2"],
        )

    def test_modo_simulacion_no_llama_al_modelo_y_respeta_umbral(self):
        motor = ClasificadorHibrido()
        motor.modo_simulacion = True
        motor.umbral_revision = "ALTA"
        with patch("clasificador_hibrido.requests.post") as llamada:
            resultado = motor.procesar_incidente("Fuga grave de aceite en CAM-101")
        llamada.assert_not_called()
        self.assertEqual(resultado["origen"], "Simulación local (solo reglas; sin llamada a Ollama)")
        self.assertTrue(resultado["requiere_revision_humana"])

    def test_experimento_evalua_30_etiquetas_sin_requerir_ollama(self):
        motor = ClasificadorHibrido()
        with patch("clasificador_hibrido.requests.get",
                   side_effect=requests.ConnectionError("offline")):
            resultado = motor.ejecutar_experimento_30_correos()
        self.assertEqual(resultado["muestras"], 30)
        self.assertFalse(resultado["llm_disponible"])
        self.assertEqual(len(resultado["resultados"]), 30)
        self.assertIsNone(resultado["metricas"]["llm"]["exactitud_categoria"])
        self.assertIsNone(resultado["metricas"]["llm"]["latencia_promedio_seg"])
        self.assertEqual(resultado["metricas"]["reglas"]["exactitud_categoria"], 1.0)


if __name__ == "__main__":
    unittest.main()
