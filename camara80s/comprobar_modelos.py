"""Comprueba que los repos de Hugging Face existen y si piden licencia.

Ejecutalo antes de la primera generacion:
    .venv\\Scripts\\python.exe comprobar_modelos.py
"""
from __future__ import annotations

import sys

import config


def _puede_descargar(repo: str, archivo: str) -> tuple[bool, str]:
    """Comprueba acceso REAL a un archivo.

    Mirar solo los metadatos del repo no sirve: en los repos de Black Forest
    Labs la ficha es publica pero los archivos devuelven 401.
    """
    from huggingface_hub import get_hf_file_metadata, hf_hub_url

    try:
        get_hf_file_metadata(hf_hub_url(repo, archivo), token=config.HF_TOKEN)
        return True, ""
    except Exception as exc:
        codigo = getattr(getattr(exc, "response", None), "status_code", None)
        if codigo in (401, 403):
            return False, "necesita permiso"
        if codigo == 404:
            return False, f"no existe el archivo {archivo}"
        return False, f"{type(exc).__name__}: {exc}"


def revisar(repo: str, etiqueta: str, filtro: str | None = None,
            archivo_prueba: str | None = None) -> bool:
    from huggingface_hub import HfApi
    from huggingface_hub.errors import RepositoryNotFoundError

    api = HfApi(token=config.HF_TOKEN)
    try:
        info = api.model_info(repo, files_metadata=False)
    except RepositoryNotFoundError:
        print(f"[NO EXISTE] {etiqueta}: {repo}")
        return False
    except Exception as exc:
        print(f"[ERROR] {etiqueta}: {repo} -> {type(exc).__name__}: {exc}")
        return False

    prueba = archivo_prueba or filtro and config.FLUX_ARCHIVO_GGUF
    if prueba:
        ok, motivo = _puede_descargar(repo, prueba)
        if not ok:
            print(f"[SIN ACCESO] {etiqueta}: {repo}  ({motivo})")
            print(f"             Entra en https://huggingface.co/{repo}, inicia")
            print("             sesion y acepta la licencia del modelo. Luego crea")
            print("             un token de lectura en /settings/tokens y ponlo en")
            print("             el .env como  HF_TOKEN=hf_...")
            return False

    print(f"[OK] {etiqueta}: {repo}")
    if filtro:
        archivos = sorted(
            s.rfilename for s in info.siblings if filtro in s.rfilename.lower()
        )
        if not archivos:
            print(f"     (sin archivos '{filtro}')")
            return False
        print(f"     {len(archivos)} archivos '{filtro}':")
        for nombre in archivos:
            marca = " <-- configurado" if nombre == config.FLUX_ARCHIVO_GGUF else ""
            print(f"       {nombre}{marca}")
        if config.FLUX_ARCHIVO_GGUF not in archivos:
            print(f"     AVISO: '{config.FLUX_ARCHIVO_GGUF}' no esta en la lista.")
            print("     Elige uno de arriba y ponlo en el .env como FLUX_ARCHIVO_GGUF.")
            return False
    return True


def main() -> None:
    print("=== comprobacion de modelos ===")
    print(f"token HF: {'si' if config.HF_TOKEN else 'no configurado'}\n")

    resultados = [
        revisar(config.FLUX_REPO_GGUF, "transformer GGUF", filtro=".gguf"),
        revisar(config.FLUX_REPO_BASE, "VAE + codificadores",
                archivo_prueba="vae/config.json"),
        revisar(config.FLUX_REPO_CONFIG, "config del transformer",
                archivo_prueba="transformer/config.json"),
    ]

    print()
    if all(resultados):
        print("Todo listo. Ya puedes ejecutar:  python main.py")
    else:
        print("Hay repos que no se pueden usar todavia. Revisa los avisos de arriba.")
        sys.exit(1)


if __name__ == "__main__":
    main()
