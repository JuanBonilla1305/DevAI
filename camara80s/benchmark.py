"""Mide cuanto tarda de verdad una generacion en esta GPU.

Carga el modelo una sola vez y prueba varias combinaciones de pasos y
resolucion, para saber donde esta el punto en que deja de merecer la pena.

    .venv\\Scripts\\python.exe benchmark.py ruta_de_una_foto.jpg
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import config


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: benchmark.py <foto>")
        sys.exit(1)

    foto = Path(sys.argv[1])
    if not foto.exists():
        print(f"No existe {foto}")
        sys.exit(1)

    import torch
    import motor_sd15
    from hardware import info_hardware

    hw = info_hardware()
    print(f"GPU: {hw['nombre']}  ({hw['vram_gb']} GB)\n")

    prompt = ("turn it into a 1985 mall studio portrait, feathered 80s hair, "
              "pastel laser background, soft focus, film grain")

    # Primera pasada: carga el modelo. No cuenta para la medida.
    print("Cargando el modelo (no se cronometra)...")
    inicio = time.time()
    motor_sd15.generar(foto, prompt, pasos=4, semilla=1)
    print(f"  carga + primera imagen: {time.time() - inicio:.1f} s\n")

    combinaciones = [
        (448, 4), (448, 8),
        (576, 4), (576, 8), (576, 12), (576, 20),
        (704, 8),
    ]

    print(f"{'resolucion':>12} {'pasos':>6} {'segundos':>10}")
    print("-" * 30)
    for lado, pasos in combinaciones:
        config.LADO_MAXIMO = lado
        inicio = time.time()
        try:
            motor_sd15.generar(foto, prompt, pasos=pasos, semilla=1)
            transcurrido = time.time() - inicio
            print(f"{lado:>12} {pasos:>6} {transcurrido:>9.1f}s")
        except torch.cuda.OutOfMemoryError:
            print(f"{lado:>12} {pasos:>6} {'sin VRAM':>10}")
            torch.cuda.empty_cache()
        except Exception as exc:
            print(f"{lado:>12} {pasos:>6}  error: {type(exc).__name__}")


if __name__ == "__main__":
    main()
