"""FLUX.2 Klein 4B en la GPU, hablando la misma API que FastSD.

Es el mismo modelo que usa el proyecto del profesor, pero en PyTorch en vez
de OpenVINO: asi corre en CUDA en lugar de en la CPU. El frontend no nota la
diferencia, solo cambia quien responde en el puerto 8000.

    FastSD / OpenVINO / CPU   ~318 s por imagen
    este servidor / CUDA      bastante menos

Como cabe en 6 GB de VRAM:

    transformer   4B params   7.2 GB en bf16  ->  ~2.3 GB en NF4
    text encoder  ~4B params  7.5 GB en bf16  ->  ~2.4 GB en NF4
    VAE                       0.2 GB en bf16

Con los dos grandes cuantizados a 4 bits y `enable_model_cpu_offload`, el
pico de VRAM se queda por debajo de los 6 GB.

    .venv\\Scripts\\python.exe servidor_flux2.py --api --port 8000
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from PIL import Image

import config

REPO = "black-forest-labs/FLUX.2-klein-4B"

_PIPE = None
# Una GPU, una generacion a la vez. Si entran dos peticiones en paralelo se
# pisan el estado del pipeline y ademas no cabrian en memoria.
_CERROJO = threading.Lock()


def _dtype():
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def _cargar():
    global _PIPE
    if _PIPE is not None:
        return _PIPE

    from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel
    from diffusers import BitsAndBytesConfig as DiffusersBnb
    from transformers import BitsAndBytesConfig as TransformersBnb
    from transformers import AutoModelForCausalLM

    dtype = _dtype()
    cuantizacion = dict(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=dtype,
    )

    print(f"[flux2] cargando {REPO}")
    print("[flux2] transformer en 4 bits")
    transformer = Flux2Transformer2DModel.from_pretrained(
        REPO,
        subfolder="transformer",
        quantization_config=DiffusersBnb(**cuantizacion),
        torch_dtype=dtype,
    )

    print("[flux2] codificador de texto en 4 bits")
    text_encoder = AutoModelForCausalLM.from_pretrained(
        REPO,
        subfolder="text_encoder",
        quantization_config=TransformersBnb(**cuantizacion),
        torch_dtype=dtype,
    )

    print("[flux2] resto del pipeline")
    pipe = Flux2KleinPipeline.from_pretrained(
        REPO,
        transformer=transformer,
        text_encoder=text_encoder,
        torch_dtype=dtype,
    )

    if torch.cuda.is_available():
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[flux2] {torch.cuda.get_device_name(0)} ({vram:.1f} GB)")
        # Cada submodelo sube a la GPU solo mientras se usa. Con 6 GB es lo
        # que permite que quepa sin tocar la velocidad demasiado.
        pipe.enable_model_cpu_offload()
    else:
        print("[flux2] AVISO: sin CUDA, esto ira lentisimo")
        pipe.to("cpu")

    if hasattr(pipe, "vae"):
        if hasattr(pipe.vae, "enable_slicing"):
            pipe.vae.enable_slicing()
        if hasattr(pipe.vae, "enable_tiling"):
            pipe.vae.enable_tiling()

    pipe.set_progress_bar_config(disable=False)
    _PIPE = pipe
    return _PIPE


def _a_imagen(dato) -> Image.Image:
    if isinstance(dato, Image.Image):
        return dato.convert("RGB")
    if "," in dato[:64]:
        dato = dato.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(dato))).convert("RGB")


def _generar(cuerpo: dict) -> dict:
    pipe = _cargar()

    entrada = cuerpo.get("init_image")
    if isinstance(entrada, (str, Image.Image)):
        entrada = [entrada]
    if not entrada:
        return {"error": "No llego ninguna imagen de referencia."}

    # server.js manda [foto de la persona, recorte(s) de cabeza, vestuario].
    # Se pasan todas: que el modelo vea la cabeza real es justo lo que
    # conserva el parecido.
    imagenes = [_a_imagen(x) for x in entrada]

    ancho = max(256, int(cuerpo.get("image_width") or 384) // 16 * 16)
    alto = max(256, int(cuerpo.get("image_height") or 512) // 16 * 16)

    pasos = max(2, min(30, int(cuerpo.get("inference_steps") or 6)))
    guia = float(cuerpo.get("guidance_scale") or 4.0)

    semilla = cuerpo.get("seed")
    if not cuerpo.get("use_seed") or semilla in (None, -1):
        semilla = int(time.time()) % 2**31
    generador = torch.Generator(device="cpu").manual_seed(int(semilla))

    inicio = time.time()
    salida = pipe(
        image=imagenes,
        prompt=(cuerpo.get("prompt") or "").strip(),
        height=alto,
        width=ancho,
        num_inference_steps=pasos,
        guidance_scale=guia,
        generator=generador,
    )
    transcurrido = time.time() - inicio

    buffer = io.BytesIO()
    salida.images[0].save(buffer, format="PNG")

    print(f"[flux2] {ancho}x{alto}, {pasos} pasos, {len(imagenes)} referencias, "
          f"semilla {semilla} -> {transcurrido:.1f} s")

    return {
        "images": [base64.b64encode(buffer.getvalue()).decode("ascii")],
        "seconds": round(transcurrido, 1),
    }


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _responder(self, codigo: int, datos: dict) -> None:
        cuerpo = json.dumps(datos).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self) -> None:
        if self.path.startswith("/api/info"):
            nombre = (
                torch.cuda.get_device_name(0)
                if torch.cuda.is_available() else "CPU"
            )
            self._responder(200, {
                "device_type": "cuda" if torch.cuda.is_available() else "cpu",
                "device_name": nombre,
                "backend": "servidor_flux2.py (FLUX.2 Klein en CUDA)",
            })
        else:
            self._responder(404, {"error": "ruta desconocida"})

    def do_POST(self) -> None:
        if not self.path.startswith("/api/generate"):
            self._responder(404, {"error": "ruta desconocida"})
            return

        try:
            largo = int(self.headers.get("Content-Length") or 0)
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        except Exception as exc:
            self._responder(400, {"error": f"cuerpo invalido: {exc}"})
            return

        try:
            with _CERROJO:
                self._responder(200, _generar(cuerpo))
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            self._responder(200, {
                "error": "Sin memoria en la GPU. Baja la resolucion."
            })
        except Exception as exc:
            traceback.print_exc()
            self._responder(200, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, formato, *args) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--api", action="store_true",
                        help="se acepta por compatibilidad con FastSD")
    parser.add_argument("--precargar", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  FLUX.2 Klein en CUDA, con la API de FastSD")
    print("=" * 60)

    if args.precargar:
        _cargar()

    servidor = ThreadingHTTPServer(("0.0.0.0", args.port), Manejador)
    print(f"Escuchando en http://127.0.0.1:{args.port}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nParado.")
        sys.exit(0)


if __name__ == "__main__":
    main()
