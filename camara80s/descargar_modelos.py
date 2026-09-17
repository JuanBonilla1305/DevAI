"""Descarga por adelantado todo lo que Flux necesita.

Asi la primera generacion no se queda 'colgada' bajando 17 GB sin avisar.
Se puede cortar con Ctrl+C y retomar: huggingface_hub reanuda lo que falte.

    .venv\\Scripts\\python.exe descargar_modelos.py
"""
from __future__ import annotations

import sys

import config

# Del repo base solo necesitamos estas carpetas, no el modelo entero.
PATRONES_BASE = [
    "vae/*",
    "text_encoder/*",
    "text_encoder_2/*",
    "tokenizer/*",
    "tokenizer_2/*",
    "scheduler/*",
    "*.json",
]


def main() -> None:
    from huggingface_hub import hf_hub_download, snapshot_download

    token = config.HF_TOKEN

    print(f"1/3  transformer GGUF  ({config.FLUX_ARCHIVO_GGUF}, ~6.8 GB)")
    hf_hub_download(
        repo_id=config.FLUX_REPO_GGUF,
        filename=config.FLUX_ARCHIVO_GGUF,
        token=token,
    )

    print("\n2/3  VAE, CLIP-L, T5-XXL y tokenizadores  (~10 GB)")
    snapshot_download(
        repo_id=config.FLUX_REPO_BASE,
        allow_patterns=PATRONES_BASE,
        token=token,
    )

    print("\n3/3  config del transformer de Kontext  (unos KB)")
    snapshot_download(
        repo_id=config.FLUX_REPO_CONFIG,
        allow_patterns=["transformer/*.json", "*.json"],
        token=token,
    )

    print("\nListo. Todo cacheado. Ahora:  python main.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido. Vuelve a ejecutarlo y sigue donde iba.")
        sys.exit(130)
