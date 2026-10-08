"""Compatibilidad con ejercicios previos; el motor de GUI vive en motor_reglas.py."""

from datetime import datetime, timezone
from typing import Any

from motor_reglas import MotorReglasLogistics


def evaluar_camion(
    P: bool,
    Q: bool,
    R: bool,
    S: bool,
    vigencia_cert: bool = True,
    horario_permitido: bool = True,
    material_peligroso: bool = False,
) -> dict[str, Any]:
    """Evalúa reglas base más certificación y restricción horaria."""
    resultado = MotorReglasLogistics().evaluar_acceso(
        P=P, Q=Q, R=R, S=S, C=vigencia_cert,
        M=material_peligroso, H=not horario_permitido,
    )
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "autorizacion": P,
        "anomalia": Q,
        "carga_prioritaria": R,
        "sello_intacto": S,
        "vigencia_cert": vigencia_cert,
        "horario_permitido": horario_permitido,
        "material_peligroso": material_peligroso,
        "acceso_estandar": resultado["A"],
        "inspeccion_especial": resultado["E"],
        "explicacion": resultado["explicacion"],
    }


if __name__ == "__main__":
    for clave, valor in evaluar_camion(True, False, False, True).items():
        print(f"{clave}: {valor}")
