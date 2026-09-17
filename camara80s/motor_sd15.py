"""Motor local de Stable Diffusion, afinado para GPUs de 6 GB."""
from __future__ import annotations

import gc
import time
from pathlib import Path

import torch
from PIL import Image, ImageOps

import config
from hardware import ahorrar_memoria, info_hardware

_PIPELINES: dict[str, object] = {}


def _liberar(excepto: str | None = None) -> None:
    """Descarga de memoria los pipelines que no vamos a usar."""
    for clave in list(_PIPELINES):
        if clave != excepto:
            del _PIPELINES[clave]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def liberar() -> None:
    """Suelta toda la memoria: la usa el enrutador al cambiar de motor."""
    _liberar(excepto=None)


def _optimizar(pipe):
    """Todo lo que hace falta para no reventar 6 GB de VRAM."""
    hw = info_hardware()
    pipe.set_progress_bar_config(disable=False)

    if hw["dispositivo"] != "cuda":
        return pipe.to("cpu")

    # Mueve cada submodelo a la GPU solo mientras se usa: es la clave en 6 GB.
    if hw["vram_gb"] < 10:
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")

    ahorrar_memoria(pipe)
    return pipe


def _cargar(modo: str):
    if modo in _PIPELINES:
        return _PIPELINES[modo]

    _liberar(excepto=None)
    from diffusers import (
        StableDiffusionImg2ImgPipeline,
        StableDiffusionInstructPix2PixPipeline,
    )

    if modo == "pix2pix":
        print(f"[modelo] cargando {config.MODELO_PIX2PIX} (la 1a vez descarga ~2.5 GB)")
        pipe = StableDiffusionInstructPix2PixPipeline.from_pretrained(
            config.MODELO_PIX2PIX,
            torch_dtype=torch.float16,
            safety_checker=None,
            requires_safety_checker=False,
        )
    else:
        print(f"[modelo] cargando {config.MODELO_IMG2IMG} (la 1a vez descarga ~2 GB)")
        pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
            config.MODELO_IMG2IMG,
            torch_dtype=torch.float16,
            safety_checker=None,
            requires_safety_checker=False,
        )

    _PIPELINES[modo] = _optimizar(pipe)
    return _PIPELINES[modo]


def _preparar(ruta: Path) -> Image.Image:
    """Corrige orientacion, recorta a 4:5 y escala a un lado multiplo de 8."""
    img = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    lado = config.LADO_MAXIMO
    escala = lado / max(img.size)
    nuevo = (
        max(8, int(img.width * escala) // 8 * 8),
        max(8, int(img.height * escala) // 8 * 8),
    )
    return img.resize(nuevo, Image.LANCZOS)


def generar(
    ruta_entrada: str | Path,
    prompt: str,
    modo: str = "pix2pix",
    negativo: str | None = None,
    pasos: int = 28,
    guia_texto: float = 7.5,
    guia_imagen: float = 1.5,
    fuerza: float = 0.5,
    semilla: int | None = None,
) -> dict:
    """Transforma la foto. Devuelve la ruta del resultado y los parametros usados."""
    entrada = Path(ruta_entrada)
    if not entrada.exists():
        raise FileNotFoundError(f"No existe la foto {entrada}")

    modo = "pix2pix" if modo not in ("pix2pix", "img2img") else modo
    pipe = _cargar(modo)
    imagen = _preparar(entrada)
    negativo = negativo or config.NEGATIVO_POR_DEFECTO

    if semilla is None:
        semilla = int(time.time()) % 2**31
    generador = torch.Generator(device="cpu").manual_seed(semilla)

    inicio = time.time()
    if modo == "pix2pix":
        salida = pipe(
            prompt=prompt,
            image=imagen,
            negative_prompt=negativo,
            num_inference_steps=pasos,
            guidance_scale=guia_texto,
            image_guidance_scale=guia_imagen,
            generator=generador,
        )
    else:
        salida = pipe(
            prompt=prompt,
            image=imagen,
            negative_prompt=negativo,
            num_inference_steps=pasos,
            guidance_scale=guia_texto,
            strength=fuerza,
            generator=generador,
        )

    resultado = salida.images[0]
    nombre = f"80s_{time.strftime('%Y%m%d_%H%M%S')}_{semilla}.png"
    destino = config.SALIDAS / nombre
    resultado.save(destino)

    return {
        "ruta": str(destino),
        "modo": modo,
        "semilla": semilla,
        "pasos": pasos,
        "guia_texto": guia_texto,
        "guia_imagen": guia_imagen if modo == "pix2pix" else None,
        "fuerza": fuerza if modo == "img2img" else None,
        "segundos": round(time.time() - inicio, 1),
    }
