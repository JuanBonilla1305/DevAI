"""Modo directo: camara -> prompt 80s -> modelo. Sin agente y sin APIs.

Sirve para dos cosas:
  - Validar que el motor de imagen funciona en esta maquina, sin depender de
    tener una API key de Anthropic.
  - Usar el programa gratis, aceptando un prompt fijo en vez de uno a medida.

    .venv\\Scripts\\python.exe main.py --directo
    .venv\\Scripts\\python.exe main.py --directo --estilo rockero
    .venv\\Scripts\\python.exe main.py --directo --foto capturas\\x.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config

# Instrucciones de edicion para Flux Kontext. Le dicen que cambiar y, sobre
# todo, que NO cambiar: ahi esta el truco para que siga pareciendose a ti.
CONSERVAR = (
    "Keep the person's facial features, bone structure, skin tone and "
    "expression exactly the same so they remain clearly recognizable."
)

ESTILOS: dict[str, str] = {
    "estudio": (
        "Restyle this photo as a 1985 American mall portrait studio photograph. "
        "Give the person voluminous feathered 80s hair, a pastel blue and pink "
        "laser beam background, and period clothing with shoulder pads. "
        "Soft focus glow, warm Kodak Gold film grain, direct studio flash. "
        + CONSERVAR
    ),
    "anuario": (
        "Restyle this photo as a 1987 high school yearbook portrait. "
        "Give the person 80s feathered hair, large gold-rimmed glasses and a "
        "collared shirt with a patterned sweater, over a mottled blue-grey "
        "studio backdrop. Slightly faded 35mm film look with warm color cast. "
        + CONSERVAR
    ),
    "rockero": (
        "Restyle this photo as a 1987 glam rock band promo shot. "
        "Give the person big teased 80s hair, a black leather studded jacket "
        "and dramatic stage lighting with magenta and cyan rim light, haze in "
        "the air. Grainy 35mm concert film look. " + CONSERVAR
    ),
    "neon": (
        "Restyle this photo as a 1984 synthwave album cover portrait. "
        "Neon magenta and cyan lighting on the face, chrome grid horizon and "
        "purple gradient sky behind, VHS scanlines and slight chromatic "
        "aberration. Keep it photographic, not illustrated. " + CONSERVAR
    ),
}

# SD 1.5 usa CLIP, que solo lee 77 tokens: lo que sobra se descarta en
# silencio. Por eso aqui van versiones cortas. Flux usa T5 y si admite los
# prompts largos de arriba.
ESTILOS_CORTOS: dict[str, str] = {
    "estudio": "turn it into a 1985 mall studio portrait, feathered 80s hair, "
               "pastel laser background, soft focus, film grain",
    "anuario": "turn it into a 1987 yearbook portrait, feathered hair, big "
               "glasses, blue-grey backdrop, faded 35mm film",
    "rockero": "turn it into a 1987 glam rock promo photo, big teased hair, "
               "leather jacket, magenta and cyan stage light",
    "neon": "turn it into a 1984 synthwave portrait, neon magenta and cyan "
            "light, chrome grid horizon, VHS scanlines",
}


def _elegir_prompt(estilo: str, motor: str) -> str:
    tabla = ESTILOS_CORTOS if motor == "sd15" else ESTILOS
    return tabla.get(estilo, tabla["estudio"])


def ejecutar(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="main.py --directo", add_help=True)
    parser.add_argument("--estilo", default="estudio", choices=sorted(ESTILOS),
                        help="estilo ochentero a aplicar")
    parser.add_argument("--foto", default=None,
                        help="usa una foto existente en vez de abrir la camara")
    parser.add_argument("--pasos", type=int, default=None)
    parser.add_argument("--guia", type=float, default=None)
    parser.add_argument("--semilla", type=int, default=None)
    args = parser.parse_args(argv)

    import generador

    motor = generador.motor_actual()
    print(f"Motor: {motor}   estilo: {args.estilo}")

    if args.foto:
        ruta = Path(args.foto)
        if not ruta.exists():
            print(f"No existe la foto {ruta}")
            return 1
    else:
        import camara
        import cv2

        print("\nSe abre la camara. ESPACIO para tomar la foto, ESC para salir.\n")
        ruta = camara.capturar()
        if ruta is None:
            print("Cancelado, no se tomo ninguna foto.")
            return 0

        metricas = camara.analizar(cv2.imread(str(ruta)))
        print(f"Foto: {ruta}")
        print(f"  caras={metricas['caras_detectadas']}  "
              f"nitidez={metricas['nitidez']}  brillo={metricas['brillo']}")
        for problema in metricas["problemas"]:
            print(f"  aviso: {problema}")

    opciones: dict = {}
    if args.pasos is not None:
        opciones["pasos"] = args.pasos
    if args.guia is not None:
        opciones["guia_texto"] = args.guia
    if args.semilla is not None:
        opciones["semilla"] = args.semilla

    prompt = _elegir_prompt(args.estilo, motor)
    print(f"\nPrompt:\n  {prompt}\n")
    print("Generando. En esta GPU Flux tarda varios minutos; no cierres la ventana.\n")

    try:
        info = generador.generar(ruta, prompt, **opciones)
    except Exception as exc:
        print(f"\nFallo la generacion: {type(exc).__name__}: {exc}")
        return 1

    print("\n--- resultado ---")
    for clave, valor in info.items():
        if valor is not None:
            print(f"  {clave}: {valor}")

    try:
        import os
        if sys.platform == "win32":
            os.startfile(info["ruta"])  # noqa: S606
    except Exception:
        pass

    return 0
