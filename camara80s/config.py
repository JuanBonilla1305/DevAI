"""Configuracion central del proyecto camara80s."""
from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CAPTURAS = RAIZ / "capturas"
SALIDAS = RAIZ / "salidas"

for _d in (CAPTURAS, SALIDAS):
    _d.mkdir(exist_ok=True)


def _cargar_env() -> None:
    """Lee un .env sencillo (CLAVE=valor) sin dependencias externas."""
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env()

# --- Agente ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODELO_AGENTE = os.environ.get("MODELO_AGENTE", "claude-sonnet-5")
MAX_TURNOS = int(os.environ.get("MAX_TURNOS", "14"))

# --- Camara ---
INDICE_CAMARA = int(os.environ.get("INDICE_CAMARA", "0"))
ANCHO_CAMARA = 1280
ALTO_CAMARA = 720

# --- Motor de imagen -------------------------------------------------------
# "flux"  -> FLUX.1 Kontext cuantizado en GGUF. Mucho mejor parecido, lento.
# "sd15"  -> Stable Diffusion 1.5 / instruct-pix2pix. Rapido, calidad menor.
MOTOR = os.environ.get("MOTOR", "flux").lower()

# --- FLUX ---
# Token de Hugging Face. Hace falta si algun repo esta "gated" (hay que
# aceptar la licencia en la web del modelo antes de poder descargarlo).
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or None

# Transformer de 12B cuantizado. Q4_K_S ocupa ~6.8 GB en disco.
# Si tu maquina va justa, baja a Q3_K_S (~5.2 GB) desde el .env.
FLUX_REPO_GGUF = os.environ.get("FLUX_REPO_GGUF", "QuantStack/FLUX.1-Kontext-dev-GGUF")
FLUX_ARCHIVO_GGUF = os.environ.get(
    "FLUX_ARCHIVO_GGUF", "flux1-kontext-dev-Q4_K_S.gguf"
)
# De donde salen el VAE y los codificadores de texto. FLUX.1-schnell es
# Apache-2.0 y NO esta gated, y comparte VAE/CLIP/T5 con Kontext.
FLUX_REPO_BASE = os.environ.get("FLUX_REPO_BASE", "black-forest-labs/FLUX.1-schnell")
# Repo con la config del transformer de Kontext (solo se leen los .json).
FLUX_REPO_CONFIG = os.environ.get(
    "FLUX_REPO_CONFIG", "black-forest-labs/FLUX.1-Kontext-dev"
)
# Cuantizar el codificador T5 a 4 bits con bitsandbytes. Pasa de ~9.8 a ~3 GB.
FLUX_T5_4BIT = os.environ.get("FLUX_T5_4BIT", "1") not in ("0", "false", "no")

# --- Stable Diffusion 1.5 ---
MODELO_PIX2PIX = os.environ.get("MODELO_PIX2PIX", "timbrooks/instruct-pix2pix")
MODELO_IMG2IMG = os.environ.get("MODELO_IMG2IMG", "Lykon/dreamshaper-8")

# Resolucion de trabajo. Flux quiere multiplos de 16; SD 1.5, de 8.
LADO_MAXIMO = int(os.environ.get("LADO_MAXIMO", "640" if MOTOR == "flux" else "576"))

NEGATIVO_POR_DEFECTO = (
    "deformed face, distorted face, extra faces, two heads, mutated hands, "
    "blurry, lowres, jpeg artifacts, text, watermark, signature, "
    "modern smartphone photo, oversaturated, cartoon, 3d render, plastic skin"
)
