"""Deteccion de GPU y ahorros de memoria, compartidos por los dos motores."""
from __future__ import annotations


def ahorrar_memoria(pipe) -> None:
    """Activa los ahorros de VRAM que existan en esta version de diffusers.

    Los helpers del pipeline (enable_vae_slicing y compania) se movieron al
    propio VAE en diffusers 0.40, asi que probamos las dos formas.
    """
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    for corto, largo in (("slicing", "vae_slicing"), ("tiling", "vae_tiling")):
        if hasattr(pipe.vae, f"enable_{corto}"):
            getattr(pipe.vae, f"enable_{corto}")()
        elif hasattr(pipe, f"enable_{largo}"):
            getattr(pipe, f"enable_{largo}")()


def info_hardware() -> dict:
    try:
        import torch
    except ImportError:
        return {"dispositivo": "?", "vram_gb": 0.0, "nombre": "PyTorch no instalado"}

    if not torch.cuda.is_available():
        return {"dispositivo": "cpu", "vram_gb": 0.0, "nombre": "sin GPU CUDA"}

    props = torch.cuda.get_device_properties(0)
    return {
        "dispositivo": "cuda",
        "vram_gb": round(props.total_memory / 1024**3, 1),
        "nombre": props.name,
    }
