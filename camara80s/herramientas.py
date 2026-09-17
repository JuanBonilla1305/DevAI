"""Herramientas que el agente puede invocar, con sus esquemas para la API."""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageOps

import camara
import config
import generador

# Lado maximo de las imagenes que le mandamos al modelo: suficiente para
# juzgar la foto sin gastar tokens de mas.
_LADO_VISION = 768


def _bloque_imagen(ruta: str | Path) -> dict:
    img = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    img.thumbnail((_LADO_VISION, _LADO_VISION), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        },
    }


def _texto(dato) -> dict:
    if not isinstance(dato, str):
        dato = json.dumps(dato, ensure_ascii=False, indent=2)
    return {"type": "text", "text": dato}


# --------------------------------------------------------------------------
# Implementaciones
# --------------------------------------------------------------------------

def _capturar_foto() -> list[dict]:
    print("\n>> Se abrio la ventana de la camara. ESPACIO para tomar la foto, ESC para cancelar.\n")
    ruta = camara.capturar()
    if ruta is None:
        return [_texto({"estado": "cancelado",
                        "detalle": "El usuario cerro la camara sin tomar foto."})]

    imagen = cv2.imread(str(ruta))
    metricas = camara.analizar(imagen)
    metricas["ruta"] = str(ruta)
    metricas["estado"] = "ok"
    return [_texto(metricas), _bloque_imagen(ruta)]


def _analizar_foto(ruta: str) -> list[dict]:
    archivo = Path(ruta)
    if not archivo.exists():
        return [_texto({"error": f"No existe el archivo {ruta}"})]
    imagen = cv2.imread(str(archivo))
    if imagen is None:
        return [_texto({"error": f"No se pudo leer la imagen {ruta}"})]
    metricas = camara.analizar(imagen)
    metricas["ruta"] = str(archivo)
    return [_texto(metricas), _bloque_imagen(archivo)]


def _generar_80s(**kwargs) -> list[dict]:
    ruta = kwargs.pop("ruta_foto")
    prompt = kwargs.pop("prompt")
    try:
        info = generador.generar(ruta, prompt, **kwargs)
    except Exception as exc:  # el agente decide si reintenta con otros valores
        return [_texto({"error": f"{type(exc).__name__}: {exc}"})]
    info["prompt_usado"] = prompt
    return [_texto(info), _bloque_imagen(info["ruta"])]


def _abrir(ruta: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(ruta)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(ruta)], check=False)
        else:
            subprocess.run(["xdg-open", str(ruta)], check=False)
    except Exception:
        pass


def _entregar_resultado(ruta: str, titulo: str, resumen: str) -> list[dict]:
    origen = Path(ruta)
    if not origen.exists():
        return [_texto({"error": f"No existe el archivo {ruta}"})]

    seguro = "".join(c if c.isalnum() or c in "-_ " else "_" for c in titulo).strip()
    seguro = (seguro or "retrato_80s").replace(" ", "_")[:60]
    destino = config.SALIDAS / f"FINAL_{seguro}{origen.suffix}"
    contador = 2
    while destino.exists():
        destino = config.SALIDAS / f"FINAL_{seguro}_{contador}{origen.suffix}"
        contador += 1

    shutil.copy2(origen, destino)
    _abrir(destino)
    print(f"\n>> Resultado final: {destino}\n   {resumen}\n")
    return [_texto({"estado": "entregado", "ruta_final": str(destino)})]


# --------------------------------------------------------------------------
# Esquemas para la API de Claude
# --------------------------------------------------------------------------

# La herramienta de generacion cambia segun el motor activo: no tiene sentido
# ofrecerle al agente parametros que su motor va a ignorar.
_FLUX = (
    "Transforma la foto al estilo de los anios 80 con FLUX.1 Kontext, que corre "
    "localmente en esta maquina. Devuelve la imagen generada para que la evalues.\n"
    "El `prompt` es una INSTRUCCION de edicion en ingles, no una descripcion. "
    "Di que cambiar y que conservar, por ejemplo: 'Restyle this portrait as a "
    "1985 mall studio photograph: give him feathered 80s hair and a pastel laser "
    "background, keep his face and expression exactly the same.'\n"
    "Kontext conserva la cara muy bien, asi que puedes pedir cambios atrevidos.\n"
    "- `guia_texto` 2.0-4.0 (por defecto 3.0). Subelo si ignora la instruccion; "
    "bajalo si la imagen sale dura o con artefactos.\n"
    "- `pasos` 20-28. Mas pasos casi no mejora y si alarga mucho la espera.\n"
    "- `negativo` solo si hace falta: DUPLICA el tiempo de generacion.\n"
    "AVISO: cada generacion tarda varios minutos en esta GPU. Piensa bien el "
    "prompt antes de lanzarla en vez de ir probando a ciegas."
)

_SD15 = (
    "Transforma la foto al estilo de los anios 80 con Stable Diffusion 1.5 local. "
    "Devuelve la imagen generada para que evalues el resultado.\n"
    "MODO 'pix2pix' (por defecto): el prompt es una INSTRUCCION en ingles, por "
    "ejemplo 'turn this into a 1980s mall studio portrait with feathered hair'. "
    "Conserva bien la cara. Sube guia_imagen (1.2-2.0) para parecerse mas al "
    "original; sube guia_texto (7-12) para que obedezca mas la instruccion.\n"
    "MODO 'img2img': el prompt DESCRIBE la imagen deseada. Estiliza mas fuerte "
    "pero puede cambiar la cara; usa fuerza 0.35-0.5 para conservar el parecido.\n"
    "IMPORTANTE: este motor lee como mucho 77 tokens (unas 55 palabras) y el "
    "resto lo descarta SIN avisar. Escribe prompts cortos y pon lo esencial al "
    "principio. Si necesitas prompts largos, el motor flux si los admite."
)

_PROPS_COMUNES = {
    "ruta_foto": {"type": "string", "description": "Ruta de la foto capturada"},
    "prompt": {"type": "string", "description": "Instruccion de edicion, en ingles"},
    "negativo": {"type": "string", "description": "Prompt negativo opcional, en ingles"},
    "semilla": {"type": "integer", "description": "Fija la semilla para repetir un resultado"},
}

if config.MOTOR == "sd15":
    _ESQUEMA_GENERAR = {
        "name": "generar_80s",
        "description": _SD15,
        "input_schema": {
            "type": "object",
            "properties": {
                **_PROPS_COMUNES,
                "modo": {"type": "string", "enum": ["pix2pix", "img2img"], "default": "pix2pix"},
                "pasos": {"type": "integer", "minimum": 12, "maximum": 50, "default": 28},
                "guia_texto": {"type": "number", "minimum": 1, "maximum": 15, "default": 7.5},
                "guia_imagen": {"type": "number", "minimum": 1, "maximum": 2.5, "default": 1.5},
                "fuerza": {"type": "number", "minimum": 0.2, "maximum": 0.8, "default": 0.5},
            },
            "required": ["ruta_foto", "prompt"],
        },
    }
else:
    _ESQUEMA_GENERAR = {
        "name": "generar_80s",
        "description": _FLUX,
        "input_schema": {
            "type": "object",
            "properties": {
                **_PROPS_COMUNES,
                "pasos": {"type": "integer", "minimum": 16, "maximum": 32, "default": 24},
                "guia_texto": {"type": "number", "minimum": 1.5, "maximum": 5, "default": 3.0},
            },
            "required": ["ruta_foto", "prompt"],
        },
    }

ESQUEMAS = [
    {
        "name": "capturar_foto",
        "description": (
            "Abre la ventana de la webcam para que la persona se tome un retrato. "
            "El usuario pulsa ESPACIO para capturar o ESC para cancelar. "
            "Devuelve la ruta, metricas de calidad (caras detectadas, nitidez, "
            "brillo, encuadre) y la foto para que la veas."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "analizar_foto",
        "description": (
            "Vuelve a medir la calidad de una foto ya guardada y te la muestra. "
            "Util si quieres revisar una captura anterior sin volver a abrir la camara."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ruta": {"type": "string", "description": "Ruta de la imagen"}},
            "required": ["ruta"],
        },
    },
    _ESQUEMA_GENERAR,
    {
        "name": "entregar_resultado",
        "description": (
            "Marca una imagen generada como resultado final: la copia con nombre "
            "legible y la abre en el visor del sistema. Llama esto UNA sola vez, "
            "cuando estes conforme con el resultado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ruta": {"type": "string", "description": "Ruta de la imagen elegida"},
                "titulo": {"type": "string", "description": "Nombre corto para el archivo"},
                "resumen": {"type": "string", "description": "Una linea explicando que lograste"},
            },
            "required": ["ruta", "titulo", "resumen"],
        },
    },
]

_DISPATCH = {
    "capturar_foto": lambda **kw: _capturar_foto(),
    "analizar_foto": lambda **kw: _analizar_foto(kw["ruta"]),
    "generar_80s": lambda **kw: _generar_80s(**kw),
    "entregar_resultado": lambda **kw: _entregar_resultado(
        kw["ruta"], kw.get("titulo", "retrato_80s"), kw.get("resumen", "")
    ),
}


def ejecutar(nombre: str, argumentos: dict) -> list[dict]:
    funcion = _DISPATCH.get(nombre)
    if funcion is None:
        return [_texto({"error": f"Herramienta desconocida: {nombre}"})]
    try:
        return funcion(**argumentos)
    except Exception as exc:
        return [_texto({"error": f"{type(exc).__name__}: {exc}"})]
