"""API simple del clasificador, compatible con los ejemplos anteriores."""

import os
from typing import Any

from clasificador_hibrido import ClasificadorHibrido
from dotenv import load_dotenv

load_dotenv()


def clasificar_con_llm(correo_texto: str) -> dict[str, Any]:
    """Devuelve el esquema compartido; usa reglas si Ollama falla o JSON no valida."""
    motor = ClasificadorHibrido(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
        model_name=os.getenv("OLLAMA_MODEL", "llama3.2"),
    )
    reglas = motor.clasificar_por_reglas(correo_texto)
    llm, latencia = motor.clasificar_con_llm(correo_texto)
    return motor.fusionar(reglas, llm, latencia)


if __name__ == "__main__":
    ejemplo = "El camión CAM-102 tiene una fuga grave de aceite."
    print(clasificar_con_llm(ejemplo))
