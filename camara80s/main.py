"""camara80s - punto de entrada.

Uso:
    python main.py                                  agente completo
    python main.py "verme como un rockero de 1987"  agente con una peticion
    python main.py --directo                        sin agente, prompt fijo
    python main.py --directo --estilo rockero       estilos: estudio, anuario,
                                                    rockero, neon
    python main.py --diagnostico                    revisa la instalacion
"""
from __future__ import annotations

import sys

import config


def _gguf_en_cache() -> str | None:
    """Ruta local del GGUF si ya esta descargado, sin tocar la red."""
    try:
        from huggingface_hub import try_to_load_from_cache
        resultado = try_to_load_from_cache(
            config.FLUX_REPO_GGUF, config.FLUX_ARCHIVO_GGUF
        )
        return resultado if isinstance(resultado, str) else None
    except Exception:
        return None


def diagnostico() -> None:
    print("=== diagnostico camara80s ===\n")

    print(f"Python      : {sys.version.split()[0]}")

    try:
        import torch
        print(f"PyTorch     : {torch.__version__}")
        print(f"CUDA        : {'si' if torch.cuda.is_available() else 'NO (ira por CPU, lentisimo)'}")
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            print(f"GPU         : {props.name} ({props.total_memory / 1024**3:.1f} GB)")
    except ImportError:
        print("PyTorch     : NO instalado")

    for paquete in ("diffusers", "transformers", "cv2", "anthropic", "PIL"):
        try:
            modulo = __import__(paquete)
            version = getattr(modulo, "__version__", "?")
            nombre = {"cv2": "opencv", "PIL": "pillow"}.get(paquete, paquete)
            print(f"{nombre:<12}: {version}")
        except ImportError:
            print(f"{paquete:<12}: NO instalado")

    print(f"API key     : {'configurada' if config.ANTHROPIC_API_KEY else 'FALTA (revisa el .env)'}")

    print(f"\nMotor       : {config.MOTOR}")
    if config.MOTOR == "flux":
        print(f"  quant     : {config.FLUX_ARCHIVO_GGUF}")
        print(f"  T5 en 4bit: {'si' if config.FLUX_T5_4BIT else 'no'}")
        ruta_gguf = _gguf_en_cache()
        print(f"  descargado: {ruta_gguf if ruta_gguf else 'NO (corre descargar_modelos.py)'}")
    print(f"  resolucion: {config.LADO_MAXIMO} px")

    try:
        import cv2
        captura = cv2.VideoCapture(config.INDICE_CAMARA, cv2.CAP_DSHOW)
        abierta = captura.isOpened()
        if abierta:
            ok, marco = captura.read()
            forma = f"{marco.shape[1]}x{marco.shape[0]}" if ok else "sin imagen"
            print(f"Camara {config.INDICE_CAMARA}    : ok ({forma})")
        else:
            print(f"Camara {config.INDICE_CAMARA}    : NO se pudo abrir")
        captura.release()
    except Exception as exc:
        print(f"Camara      : error -> {exc}")

    print("\nSi todo sale bien, ejecuta:  python main.py")


def main() -> None:
    argumentos = sys.argv[1:]

    if argumentos and argumentos[0] in ("--diagnostico", "-d"):
        diagnostico()
        return

    if argumentos and argumentos[0] == "--directo":
        import directo
        sys.exit(directo.ejecutar(argumentos[1:]))

    peticion = " ".join(argumentos).strip() or (
        "Tomame una foto con la webcam y conviérteme en un retrato de los anios 80."
    )

    print("=" * 66)
    print("  camara80s - tu retrato ochentero, generado en tu propia maquina")
    print("=" * 66)

    import agente

    try:
        agente.ejecutar(peticion)
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
    finally:
        print(f"Capturas en : {config.CAPTURAS}")
        print(f"Resultados  : {config.SALIDAS}")


if __name__ == "__main__":
    main()
