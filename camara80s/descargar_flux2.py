"""Descarga FLUX.2 Klein 4B en formato diffusers, para correrlo en la GPU.

El modelo que usa FastSD es el mismo pero exportado a OpenVINO, que solo
corre en CPU. Este es el original en PyTorch, que sí aprovecha CUDA.

Se salta `flux-2-klein-4b.safetensors`: son los mismos pesos del transformer
en un único archivo, 7,2 GB que no hacen falta porque ya vienen en la carpeta
transformer/.

    .venv\\Scripts\\python.exe descargar_flux2.py
"""
from __future__ import annotations

import sys

REPO = "black-forest-labs/FLUX.2-klein-4B"

PATRONES = [
    "model_index.json",
    "transformer/*",
    "text_encoder/*",
    "tokenizer/*",
    "vae/*",
    "scheduler/*",
]

IGNORAR = ["flux-2-klein-4b.safetensors"]


def main() -> None:
    from huggingface_hub import snapshot_download

    print(f"Descargando {REPO} (~15 GB)")
    print("Se puede cortar con Ctrl+C y retomar donde iba.\n")

    ruta = snapshot_download(
        repo_id=REPO,
        allow_patterns=PATRONES,
        ignore_patterns=IGNORAR,
    )
    print(f"\nListo en:\n{ruta}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido. Vuelve a ejecutarlo y sigue donde iba.")
        sys.exit(130)
