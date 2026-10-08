"""Motor proposicional para la autorización e inspección de transporte."""

from itertools import product
from typing import Any


class MotorReglasLogistics:
    """Evalúa reglas base y dos extensiones de seguridad justificadas."""

    def evaluar_acceso(
        self,
        P: bool,
        Q: bool,
        R: bool,
        S: bool,
        C: bool = True,
        M: bool = False,
        H: bool = False,
    ) -> dict[str, Any]:
        """
        P: autorización, Q: anomalía, R: carga prioritaria, S: sello intacto.
        C: certificación vigente, M: material peligroso, H: horario restringido.
        """
        base_A = P and S and not Q
        base_E = P and (R or Q)
        regla_certificacion = not C
        regla_horario = M and H

        acceso = base_A and C and not regla_horario
        inspeccion = base_E or regla_certificacion or regla_horario
        pasos = [
            f"Premisas: P={P}, Q={Q}, R={R}, S={S}, C={C}, M={M}, H={H}.",
            f"Regla base A = P ∧ S ∧ ¬Q: {P} ∧ {S} ∧ ¬{Q} = {base_A}.",
            f"Regla base E = P ∧ (R ∨ Q): {P} ∧ ({R} ∨ {Q}) = {base_E}.",
            "R3 (ampliación): certificación vigente requerida para acceso normal; "
            f"C={C}, por tanto bloqueo={regla_certificacion}.",
            "R4 (ampliación): material peligroso en horario restringido requiere "
            f"inspección; M ∧ H = {regla_horario}.",
        ]
        if not acceso:
            causas = []
            if not P:
                causas.append("falta autorización")
            if not S:
                causas.append("sello de seguridad no intacto")
            if Q:
                causas.append("anomalía reportada")
            if not C:
                causas.append("certificación vencida")
            if regla_horario:
                causas.append("material peligroso en horario restringido")
            pasos.append("Acceso normal denegado: " + ", ".join(causas) + ".")
        else:
            pasos.append("Acceso normal permitido: se cumplen todas las condiciones.")
        pasos.append(
            "Inspección especial requerida." if inspeccion
            else "No se requiere inspección especial."
        )
        return {
            "A": acceso,
            "E": inspeccion,
            "explicacion": "\n".join(pasos),
            "reglas": {"A_base": base_A, "E_base": base_E,
                       "certificacion_vigente": C, "horario_restringido": regla_horario},
        }

    def generar_tabla_verdad(self) -> list[dict[str, str]]:
        """Tabla completa de reglas base P/Q/R/S con V/F (16 combinaciones)."""
        tabla = []
        for P, Q, R, S in product([False, True], repeat=4):
            resultado = self.evaluar_acceso(P, Q, R, S)
            tabla.append({
                "P": "V" if P else "F",
                "Q": "V" if Q else "F",
                "R": "V" if R else "F",
                "S": "V" if S else "F",
                "A": "V" if resultado["A"] else "F",
                "E": "V" if resultado["E"] else "F",
            })
        return tabla
