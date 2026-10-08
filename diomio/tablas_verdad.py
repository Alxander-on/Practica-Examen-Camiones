# ============================================================
# TABLA DE VERDAD DEL SISTEMA LOGISMART
# ============================================================

def generar_tabla_verdad():
    """Imprime la tabla base y las tablas de las dos extensiones R3/R4."""
    from itertools import product

    def vf(valor: bool) -> str:
        return "V" if valor else "F"

    print("\nTABLA BASE: A=P∧S∧¬Q; E=P∧(R∨Q)")
    print("P Q R S | A | E")
    for P, Q, R, S in product([False, True], repeat=4):
        print(f"{vf(P)} {vf(Q)} {vf(R)} {vf(S)} | "
              f"{vf(P and S and not Q)} | {vf(P and (R or Q))}")

    print("\nR3: certificación C requerida para acceso normal (A'=A∧C)")
    print("A_base C | A_final | E_cert")
    for A_base, C in product([False, True], repeat=2):
        print(f"   {vf(A_base)}     {vf(C)} |    {vf(A_base and C)}    |    {vf(not C)}")

    print("\nR4: M∧H bloquea acceso normal y requiere inspección")
    print("M H | bloqueo | A_control | E_control")
    for M, H in product([False, True], repeat=2):
        bloqueo = M and H
        print(f"{vf(M)} {vf(H)} |    {vf(bloqueo)}    |     {vf(not bloqueo)}      |     {vf(bloqueo)}")


if __name__ == "__main__":
    generar_tabla_verdad()