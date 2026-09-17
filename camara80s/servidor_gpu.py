"""Servidor compatible con la API de FastSD, pero generando en la GPU.

El frontend de sanjuanero-node habla con FastSD por HTTP en el puerto 8000.
Este servidor responde igual, asi que server.js no distingue la diferencia,
pero por dentro genera con CUDA en vez de OpenVINO/CPU.

    10 minutos por imagen  ->  unos 6 segundos

Contrato que hay que cumplir (lo impone server.js):
    GET  /api/info      cualquier 200; sirve para saber que ya arranco
    POST /api/generate  recibe el cuerpo de buildFastSDBody() y devuelve
                        {"images": ["<base64>"]} o {"error": "..."}

    .venv\\Scripts\\python.exe servidor_gpu.py --port 8000
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

_PIPE = None

# El pipeline y su scheduler tienen estado interno. Si dos peticiones entran a
# la vez se pisan y salen errores de indices fuera de rango, asi que se genera
# de una en una. En una sola GPU tampoco se ganaria nada en paralelo.
_CERROJO = threading.Lock()


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def _cargar():
    """Carga el modelo en la GPU. Se hace una sola vez.

    Se usa img2img y no instruct-pix2pix. pix2pix interpreta el prompt como
    una orden ("ponle un blazer") y, con ordenes de vestuario, acaba
    generando la prenda sola y tirando a la persona. img2img parte de la
    foto con ruido controlado: la composicion queda sujeta por construccion
    y la fuerza del cambio se regula con un unico valor.
    """
    global _PIPE
    if _PIPE is not None:
        return _PIPE

    from diffusers import StableDiffusionImg2ImgPipeline
    from hardware import ahorrar_memoria

    print(f"[gpu] cargando {config.MODELO_IMG2IMG}")
    pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
        config.MODELO_IMG2IMG,
        torch_dtype=torch.float16,
        safety_checker=None,
        requires_safety_checker=False,
    )

    if torch.cuda.is_available():
        pipe = pipe.to("cuda")
        print(f"[gpu] en {torch.cuda.get_device_name(0)}")
    else:
        print("[gpu] AVISO: no hay CUDA, esto ira por CPU y sera lento")

    ahorrar_memoria(pipe)
    pipe.set_progress_bar_config(disable=True)
    _PIPE = pipe
    return _PIPE


def _embeddings_largos(pipe, texto: str):
    """Codifica un prompt de cualquier longitud.

    CLIP solo acepta 77 tokens y diffusers descarta el resto sin avisar. Los
    prompts de este proyecto pasan de 200, asi que el texto se trocea en
    ventanas de 75 tokens, se codifica cada una por separado y se concatenan
    los embeddings. El modelo recibe entonces el prompt entero.
    """
    tokenizer = pipe.tokenizer
    codificador = pipe.text_encoder
    dispositivo = codificador.device

    maximo = tokenizer.model_max_length  # 77 = 75 + inicio + fin
    hueco = maximo - 2

    ids = tokenizer(texto, truncation=False, add_special_tokens=False).input_ids
    if not ids:
        ids = [tokenizer.eos_token_id]

    trozos = [ids[i:i + hueco] for i in range(0, len(ids), hueco)]

    partes = []
    for trozo in trozos:
        relleno = [tokenizer.eos_token_id] * (hueco - len(trozo))
        completo = (
            [tokenizer.bos_token_id] + trozo + relleno + [tokenizer.eos_token_id]
        )
        tensor = torch.tensor([completo], device=dispositivo)
        with torch.no_grad():
            partes.append(codificador(tensor)[0])

    return torch.cat(partes, dim=1)


def _a_imagen(dato: str) -> Image.Image:
    """Convierte un base64 (con o sin cabecera data:) en imagen RGB."""
    if "," in dato[:64]:
        dato = dato.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(dato))).convert("RGB")


def _encuadrar(img: Image.Image, ancho: int, alto: int) -> Image.Image:
    """Recorta a la proporcion pedida centrando en la cara, y luego escala.

    Estirar la foto hasta el tamanio de salida la deforma: una foto apaisada
    aplastada a formato retrato saca la cara descentrada y cortada. Aqui se
    busca la cara, se recorta un busto a su alrededor respetando la
    proporcion, y solo entonces se escala.
    """
    import cv2
    import numpy as np

    proporcion = ancho / alto
    W, H = img.size

    try:
        import camara
        caras = camara.detectar_caras(
            cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        )
    except Exception as exc:
        # Sin este aviso el fallo pasa desapercibido: se recorta por el centro
        # y el resultado sale mal encuadrado sin que nada lo explique.
        print(f"[gpu] AVISO: fallo la deteccion de caras -> "
              f"{type(exc).__name__}: {exc}")
        caras = []

    if caras:
        x, y, w, h = max(caras, key=lambda c: c[2] * c[3])
        cx = x + w / 2
        # El centro vertical se baja un poco: en un retrato de busto la cara
        # va en el tercio superior, no en el medio.
        cy = y + h * 1.15

        # Encuadre algo mas abierto que un primer plano: InSwapper trabaja a
        # 128x128, asi que cuanto mas grande sale la cara en la imagen final,
        # mas se nota el desenfoque del intercambio. Dejando mas cuerpo la
        # cara ocupa menos pixeles y el pegado pasa desapercibido.
        caja_alto = min(H, h * 5.0)
        caja_ancho = caja_alto * proporcion
        if caja_ancho > W:
            caja_ancho = W
            caja_alto = caja_ancho / proporcion
    else:
        # Sin cara detectada, recorte central a la proporcion pedida.
        cx, cy = W / 2, H / 2
        if W / H > proporcion:
            caja_alto, caja_ancho = H, H * proporcion
        else:
            caja_ancho, caja_alto = W, W / proporcion

    izquierda = int(round(min(max(0, cx - caja_ancho / 2), W - caja_ancho)))
    arriba = int(round(min(max(0, cy - caja_alto / 2), H - caja_alto)))
    recorte = img.crop((
        izquierda,
        arriba,
        izquierda + int(round(caja_ancho)),
        arriba + int(round(caja_alto)),
    ))

    print(f"[gpu] encuadre: {W}x{H} -> recorte {recorte.size[0]}x{recorte.size[1]}"
          f" ({'cara detectada' if caras else 'centro'}) -> {ancho}x{alto}")
    return recorte.resize((ancho, alto), Image.LANCZOS)


def _generar(cuerpo: dict) -> dict:
    pipe = _cargar()

    entrada = cuerpo.get("init_image")
    if isinstance(entrada, str):
        entrada = [entrada]
    if not entrada:
        return {"error": "No llego ninguna imagen de referencia."}

    # server.js manda [pose, cabeza(s), vestuario]. Usamos la primera como
    # base: la identidad no depende de esto, porque el propio frontend pega
    # la cara real con InSwapper despues de generar.
    base = _a_imagen(entrada[0])

    ancho = int(cuerpo.get("image_width") or 384)
    alto = int(cuerpo.get("image_height") or 512)
    ancho = max(256, ancho // 8 * 8)
    alto = max(256, alto // 8 * 8)
    base = _encuadrar(base, ancho, alto)

    pasos = max(4, min(30, int(cuerpo.get("inference_steps") or 20)))

    # FastSD manda guidance 1.0 porque FLUX.2 lo necesita asi. SD 1.5 con ese
    # valor ignora el prompt, asi que lo subimos a un rango util.
    guia = float(cuerpo.get("guidance_scale") or 1.0)
    if guia < 3.0:
        guia = 8.0

    # Cuanto del original se conserva. 0 = no cambia nada, 1 = imagen nueva.
    # Por debajo de 0.35 apenas se nota el cambio; por encima de 0.6 se
    # pierde la persona.
    fuerza = float(cuerpo.get("strength") or 0.72)
    fuerza = max(0.2, min(0.90, fuerza))

    semilla = cuerpo.get("seed")
    if not cuerpo.get("use_seed") or semilla in (None, -1):
        semilla = int(time.time()) % 2**31
    generador = torch.Generator(device="cpu").manual_seed(int(semilla))

    prompt = (cuerpo.get("prompt") or "").strip()
    negativo = (cuerpo.get("negative_prompt") or "").strip()
    negativo = negativo or config.NEGATIVO_POR_DEFECTO

    embeddings = _embeddings_largos(pipe, prompt)
    embeddings_neg = _embeddings_largos(pipe, negativo)
    # Los dos tienen que medir lo mismo para poder aplicar guidance.
    if embeddings_neg.shape[1] < embeddings.shape[1]:
        repeticiones = -(-embeddings.shape[1] // embeddings_neg.shape[1])
        embeddings_neg = embeddings_neg.repeat(1, repeticiones, 1)
    embeddings_neg = embeddings_neg[:, : embeddings.shape[1], :]

    inicio = time.time()
    # Scheduler nuevo en cada peticion: el del pipeline guarda el paso actual
    # y, si una generacion falla a medias, la siguiente hereda ese estado y
    # se sale del array de timesteps.
    pipe.scheduler = pipe.scheduler.from_config(pipe.scheduler.config)
    salida = pipe(
        prompt_embeds=embeddings,
        negative_prompt_embeds=embeddings_neg,
        image=base,
        num_inference_steps=pasos,
        guidance_scale=guia,
        strength=fuerza,
        generator=generador,
    )
    transcurrido = time.time() - inicio

    buffer = io.BytesIO()
    salida.images[0].save(buffer, format="PNG")
    codificada = base64.b64encode(buffer.getvalue()).decode("ascii")

    print(f"[gpu] {ancho}x{alto}, {pasos} pasos, guia {guia}, fuerza {fuerza}, "
          f"semilla {semilla} -> {transcurrido:.1f} s")

    return {"images": [codificada], "seconds": round(transcurrido, 1)}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

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
                "backend": "servidor_gpu.py (diffusers CUDA)",
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
            # El traceback va al log del servidor; al frontend solo el mensaje.
            traceback.print_exc()
            self._responder(200, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, formato, *args) -> None:
        pass  # el log util lo imprimimos nosotros en _generar


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--api", action="store_true",
                        help="se acepta por compatibilidad con FastSD")
    parser.add_argument("--precargar", action="store_true",
                        help="carga el modelo al arrancar en vez de en la "
                             "primera peticion")
    args = parser.parse_args()

    print("=" * 60)
    print("  Motor GPU compatible con la API de FastSD")
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
