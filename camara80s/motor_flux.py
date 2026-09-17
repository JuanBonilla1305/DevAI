"""FLUX.1 Kontext cuantizado en GGUF, armado para caber en 6 GB de VRAM.

Kontext es un modelo de EDICION: recibe la foto y una instruccion en ingles
("turn this into a 1980s studio portrait") y conserva la identidad de la cara
mucho mejor que un img2img normal.

El modelo completo son 12.000 millones de parametros (~24 GB en bf16). Aqui
se usa en tres piezas:

  transformer   GGUF Q4  ~6.8 GB   el grueso del modelo
  T5-XXL        NF4      ~3.0 GB   codificador de texto largo
  VAE + CLIP-L  bf16     ~0.4 GB   del repo de FLUX.1-schnell (sin licencia)

Con `enable_sequential_cpu_offload` cada submodulo sube a la GPU solo mientras
se ejecuta, asi que la VRAM pico se mantiene por debajo de 6 GB a costa de
velocidad: entre 3 y 8 minutos por imagen en una RTX 3050 portatil.
"""
from __future__ import annotations

import gc
import time
from pathlib import Path

import torch
from PIL import Image, ImageOps

import config
from hardware import ahorrar_memoria

_PIPE = None


def _dtype() -> torch.dtype:
    """bfloat16 si la GPU lo soporta (Ampere en adelante); si no, float16."""
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def _url_gguf() -> str:
    return (
        f"https://huggingface.co/{config.FLUX_REPO_GGUF}"
        f"/blob/main/{config.FLUX_ARCHIVO_GGUF}"
    )


def liberar() -> None:
    global _PIPE
    _PIPE = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _cargar_transformer(dtype):
    from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig

    print(f"[flux] transformer GGUF: {config.FLUX_ARCHIVO_GGUF}")
    return FluxTransformer2DModel.from_single_file(
        _url_gguf(),
        quantization_config=GGUFQuantizationConfig(compute_dtype=dtype),
        config=config.FLUX_REPO_CONFIG,
        subfolder="transformer",
        torch_dtype=dtype,
        token=config.HF_TOKEN,
    )


def _cargar_t5(dtype):
    from transformers import T5EncoderModel

    kwargs = {"subfolder": "text_encoder_2", "torch_dtype": dtype,
              "token": config.HF_TOKEN}

    if config.FLUX_T5_4BIT:
        try:
            from transformers import BitsAndBytesConfig
            import bitsandbytes  # noqa: F401  solo para fallar temprano

            print("[flux] T5-XXL en 4 bits (NF4)")
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=dtype,
            )
        except ImportError:
            print("[flux] aviso: falta bitsandbytes, cargo T5 completo (~9.8 GB)")

    return T5EncoderModel.from_pretrained(config.FLUX_REPO_BASE, **kwargs)


def _construir():
    """Arma el pipeline pieza por pieza y lo deja listo para generar."""
    from diffusers import AutoencoderKL, FluxKontextPipeline
    from diffusers.schedulers import FlowMatchEulerDiscreteScheduler
    from transformers import CLIPTextModel, CLIPTokenizer, T5TokenizerFast

    dtype = _dtype()
    base = config.FLUX_REPO_BASE
    tok = config.HF_TOKEN

    print("[flux] primera vez: se descargan ~11 GB a ~/.cache/huggingface")

    transformer = _cargar_transformer(dtype)
    text_encoder_2 = _cargar_t5(dtype)

    print("[flux] VAE, CLIP-L y tokenizadores")
    vae = AutoencoderKL.from_pretrained(base, subfolder="vae",
                                        torch_dtype=dtype, token=tok)
    text_encoder = CLIPTextModel.from_pretrained(base, subfolder="text_encoder",
                                                 torch_dtype=dtype, token=tok)
    tokenizer = CLIPTokenizer.from_pretrained(base, subfolder="tokenizer", token=tok)
    tokenizer_2 = T5TokenizerFast.from_pretrained(base, subfolder="tokenizer_2",
                                                  token=tok)
    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
        base, subfolder="scheduler", token=tok
    )

    pipe = FluxKontextPipeline(
        scheduler=scheduler,
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        text_encoder_2=text_encoder_2,
        tokenizer_2=tokenizer_2,
        transformer=transformer,
    )

    vram = 0.0
    if torch.cuda.is_available():
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3

    if not torch.cuda.is_available():
        print("[flux] sin GPU: esto va a tardar muchisimo")
        pipe.to("cpu")
    elif vram < 8:
        # Unica opcion realista en 6 GB: subir un submodulo a la vez.
        print(f"[flux] {vram:.1f} GB de VRAM -> offload secuencial (lento pero cabe)")
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.enable_model_cpu_offload()

    ahorrar_memoria(pipe)
    pipe.set_progress_bar_config(disable=False)
    return pipe


def _obtener():
    global _PIPE
    if _PIPE is None:
        _PIPE = _construir()
    return _PIPE


def _preparar(ruta: Path) -> Image.Image:
    """Escala la foto a un tamanio con lados multiplos de 16 (lo que quiere Flux)."""
    img = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    escala = config.LADO_MAXIMO / max(img.size)
    ancho = max(256, int(img.width * escala) // 16 * 16)
    alto = max(256, int(img.height * escala) // 16 * 16)
    return img.resize((ancho, alto), Image.LANCZOS)


def generar(
    ruta_entrada: str | Path,
    prompt: str,
    negativo: str | None = None,
    pasos: int = 24,
    guia_texto: float = 3.0,
    semilla: int | None = None,
    **_ignorado,
) -> dict:
    """Aplica la instruccion a la foto. Devuelve la ruta del resultado."""
    entrada = Path(ruta_entrada)
    if not entrada.exists():
        raise FileNotFoundError(f"No existe la foto {entrada}")

    pipe = _obtener()
    imagen = _preparar(entrada)

    if semilla is None:
        semilla = int(time.time()) % 2**31
    generador = torch.Generator(device="cpu").manual_seed(semilla)

    llamada = {
        "image": imagen,
        "prompt": prompt,
        "height": imagen.height,
        "width": imagen.width,
        "num_inference_steps": pasos,
        "guidance_scale": guia_texto,
        "generator": generador,
    }
    # Flux no usa CFG clasico: el prompt negativo solo aplica si activamos
    # true CFG, que duplica el tiempo de generacion. Solo si nos lo piden.
    if negativo:
        llamada["negative_prompt"] = negativo
        llamada["true_cfg_scale"] = 2.0

    inicio = time.time()
    resultado = pipe(**llamada).images[0]

    nombre = f"80s_flux_{time.strftime('%Y%m%d_%H%M%S')}_{semilla}.png"
    destino = config.SALIDAS / nombre
    resultado.save(destino)

    return {
        "ruta": str(destino),
        "motor": "flux-kontext-gguf",
        "semilla": semilla,
        "pasos": pasos,
        "guia_texto": guia_texto,
        "cfg_real": bool(negativo),
        "resolucion": f"{imagen.width}x{imagen.height}",
        "segundos": round(time.time() - inicio, 1),
    }
