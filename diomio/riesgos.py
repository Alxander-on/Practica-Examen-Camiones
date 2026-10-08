# ============================================================
# EVALUACIÓN ÉTICA Y MATRIZ DE RIESGOS (riesgos.py)
# ============================================================

import json
import os
import matplotlib.pyplot as plt

class EvaluadorRiesgosIA:
    """
    Clase encargada de registrar, calcular, graficar y exportar
    los riesgos éticos de un sistema de IA.
    """

    ESCALA = {"Bajo": 1, "Baja": 1, "Medio": 3, "Media": 3, "Alto": 5, "Alta": 5}

    def __init__(self):
        self.riesgos = []

    def _calcular_puntaje(self, impacto, probabilidad):
        i_val = self.ESCALA.get(impacto, 3)
        p_val = self.ESCALA.get(probabilidad, 3)
        score = i_val * p_val
        if score <= 6:
            nivel = "Bajo"
            color = "green"
        elif score <= 15:
            nivel = "Medio"
            color = "orange"
        else:
            nivel = "Alto"
            color = "red"
        return score, nivel, color

    def registrar_riesgo(self, modulo, riesgo, categoria, impacto, probabilidad, mitigacion):
        score, nivel, color = self._calcular_puntaje(impacto, probabilidad)
        riesgo_nuevo = {
            "modulo": modulo,
            "riesgo": riesgo,
            "categoria": categoria,
            "impacto": impacto,
            "probabilidad": probabilidad,
            "score": score,
            "nivel": nivel,
            "color": color,
            "mitigacion": mitigacion
        }
        self.riesgos.append(riesgo_nuevo)

    def mostrar_riesgos(self):
        print("\n========================================")
        print("       MATRIZ DE RIESGOS DE IA")
        print("========================================")
        for numero, riesgo in enumerate(self.riesgos, start=1):
            print(f"\nRiesgo #{numero}")
            print("Módulo:", riesgo["modulo"])
            print("Riesgo:", riesgo["riesgo"])
            print("Categoría:", riesgo["categoria"])
            print(f"Puntaje: {riesgo['score']} ({riesgo['nivel']})")
            print("Mitigación:", riesgo["mitigacion"])

    def generar_grafico_matriz(self, ruta="reportes/matriz_riesgos.png"):
        if not self.riesgos:
            return
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        nombres = [r["modulo"] for r in self.riesgos]
        scores = [r["score"] for r in self.riesgos]
        colores = [r["color"] for r in self.riesgos]

        plt.figure(figsize=(7, 4))
        plt.bar(nombres, scores, color=colores, edgecolor="black")
        plt.title("Matriz de Riesgos Éticos (Impacto x Probabilidad)")
        plt.ylabel("Puntaje")
        plt.ylim(0, 25)
        plt.grid(axis="y", linestyle=":", alpha=0.6)
        plt.tight_layout()
        plt.savefig(ruta)
        plt.close()
        print(f"\nGráfico guardado en: {ruta}")

    def exportar_reporte(self, archivo):
        carpeta = os.path.dirname(archivo)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)

        reporte = {
            "total_riesgos": len(self.riesgos),
            "riesgos": self.riesgos
        }

        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(reporte, f, indent=4, ensure_ascii=False)

        print(f"\nReporte exportado correctamente en: {archivo}")

if __name__ == "__main__":
    evaluador = EvaluadorRiesgosIA()
    evaluador.registrar_riesgo(
        modulo="Cámara de detección",
        riesgo="Sesgo en condiciones nocturnas",
        categoria="Sesgo",
        impacto="Alto",
        probabilidad="Media",
        mitigacion="Realizar pruebas con diferentes condiciones de iluminación"
    )
    evaluador.mostrar_riesgos()
    evaluador.generar_grafico_matriz()
    evaluador.exportar_reporte("reportes/reporte_riesgos.json")