"""Enrutador entre los motores de imagen disponibles.

MOTOR=flux  -> FLUX.1 Kontext GGUF (motor_flux.py).  Mejor parecido, lento.
MOTOR=sd15  -> Stable Diffusion 1.5 (motor_sd15.py). Rapido, calidad menor.

Ambos son locales: ninguna foto sale de la maquina.
"""
from __future__ import annotations

import config
from hardware import info_hardware  # noqa: F401  se reexporta a proposito

_ACTIVO: str | None = None


def motor_actual() -> str:
    return config.MOTOR if config.MOTOR in ("flux", "sd15") else "flux"


def _modulo(nombre: str):
    """Carga el motor pedido y descarga el otro para no duplicar memoria."""
    global _ACTIVO

    if nombre == "flux":
        import motor_flux as modulo
        if _ACTIVO == "sd15":
            import motor_sd15
            motor_sd15.liberar()
    else:
        import motor_sd15 as modulo
        if _ACTIVO == "flux":
            import motor_flux
            motor_flux.liberar()

    _ACTIVO = nombre
    return modulo


def generar(ruta_entrada, prompt: str, **opciones) -> dict:
    """Genera la imagen con el motor configurado.

    Las opciones que no aplican al motor activo se ignoran, para que el agente
    pueda mandar siempre el mismo juego de parametros.
    """
    nombre = opciones.pop("motor", None) or motor_actual()
    if nombre not in ("flux", "sd15"):
        nombre = motor_actual()

    if nombre == "sd15":
        # El agente elige pix2pix o img2img dentro de SD 1.5.
        opciones.setdefault("modo", "pix2pix")
    else:
        opciones.pop("modo", None)
        opciones.pop("guia_imagen", None)
        opciones.pop("fuerza", None)

    return _modulo(nombre).generar(ruta_entrada, prompt, **opciones)
