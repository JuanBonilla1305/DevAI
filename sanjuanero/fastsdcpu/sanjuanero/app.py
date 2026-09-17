"""Interfaz local de Sanjuanero IA."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

import gradio as gr
from PIL import Image

from sanjuanero.detect import SCENE_CHOICES, detect_people, normalize_scene
from sanjuanero.face_preserve import preserve_face
from sanjuanero.generate import generate_sanjuanero, load_costume_reference
from sanjuanero.prompts import build_prompt

CSS = """
.gradio-container {max-width: 1100px !important;}
footer {visibility: hidden}
#titulo h1 {font-size: 2rem; margin-bottom: 0.2rem;}
"""


def analyze_photo(image: Image.Image):
    if image is None:
        return None, gr.update(), "Sube una foto de una o dos personas.", ""

    result = detect_people(image)
    prompt = build_prompt(
        result.scene,
        has_costume_ref=load_costume_reference(result.scene) is not None,
    )
    return result.annotated, result.scene, result.message, prompt


def generate_photo(
    image: Image.Image,
    costume: Image.Image,
    scene: str,
    steps: int,
    max_size: int,
    keep_face: bool,
):
    if image is None:
        yield None, "Sube una foto primero.", ""
        return

    scene = normalize_scene(scene)
    prompt = build_prompt(
        scene,
        has_costume_ref=costume is not None or load_costume_reference(scene) is not None,
    )
    yield (
        None,
        (
            "Generando el Sanjuanero en tu PC. "
            "En CPU esto puede tardar entre 8 y 25 minutos. "
            "No cierres esta ventana."
        ),
        prompt,
    )

    result, latency, prompt, face_ok = generate_sanjuanero(
        image=image,
        scene=scene,
        steps=int(steps),
        max_size=int(max_size),
        costume=costume,
        keep_face=bool(keep_face),
    )
    if result is None:
        yield None, "No se pudo generar la imagen. Revisa la consola para ver el error.", prompt
        return

    minutes = latency / 60 if latency else 0
    face_msg = (
        " Se pegó el rostro original."
        if face_ok
        else " No se pudo pegar el rostro; usa el botón 3."
    )
    yield (
        result,
        f"Listo. Tardó {minutes:.1f} minutos.{face_msg} Guardada en results.",
        prompt,
    )


def paste_face_only(original: Image.Image, generated: Image.Image):
    if original is None:
        return generated, "Sube primero la foto original."
    if generated is None:
        return None, "Genera una imagen o espera a que termine."
    result, ok = preserve_face(original, generated)
    if ok:
        return result, "Rostro original pegado. No hace falta volver a generar con FLUX."
    return generated, "No encontré las dos caras. Usa una foto de frente y un resultado donde se vea el rostro."


def get_ui() -> gr.Blocks:
    with gr.Blocks(title="Sanjuanero IA") as demo:
        gr.Markdown(
            """
            # Sanjuanero IA
            Sube la **foto de la persona** y, si quieres, otra del **traje**.
            FLUX usa el vestuario de referencia y después se pega el rostro original.
            """,
            elem_id="titulo",
        )

        with gr.Row():
            with gr.Column():
                photo = gr.Image(
                    label="Foto original",
                    type="pil",
                    sources=["upload", "webcam", "clipboard"],
                )
                analyze_btn = gr.Button("1. Analizar foto", variant="secondary")
                scene = gr.Radio(
                    SCENE_CHOICES,
                    value="Mujer",
                    label="¿Cómo vestirlos?",
                    info="Se llena solo al analizar. Puedes corregirlo antes de generar.",
                )
                with gr.Accordion("Ajustes (opcional)", open=False):
                    steps = gr.Slider(
                        2,
                        8,
                        value=4,
                        step=1,
                        label="Pasos de generación",
                        info="4 es más rápido. 8 tarda más y no siempre queda mejor.",
                    )
                    max_size = gr.Slider(
                        384,
                        768,
                        value=512,
                        step=128,
                        label="Tamaño máximo",
                        info="Con foto de traje usa 512. 768 puede quedarse sin memoria RAM.",
                    )
                costume = gr.Image(
                    value=load_costume_reference("Mujer"),
                    label="Foto del traje típico (referencia)",
                    type="pil",
                    sources=["upload", "clipboard"],
                    height=280,
                )
                keep_face = gr.Checkbox(
                    value=True,
                    label="Pegar el rostro original al final",
                    info="Recomendado. FLUX suele cambiar la cara; esto la devuelve.",
                )
                generate_btn = gr.Button("2. Generar imagen Sanjuanero", variant="primary")
                status = gr.Markdown("Sube una foto y pulsa Analizar.")
                prompt_box = gr.Textbox(
                    label="Instrucción que se le envía al modelo",
                    lines=8,
                    interactive=False,
                )

            with gr.Column():
                preview = gr.Image(
                    label="Detección (rostros y género)",
                    type="pil",
                    interactive=False,
                )
                result = gr.Image(
                    label="Imagen generada (puedes soltar aquí un resultado anterior)",
                    type="pil",
                    sources=["upload", "clipboard"],
                )
                paste_btn = gr.Button("3. Pegar mi rostro en el resultado")

        analyze_btn.click(
            fn=analyze_photo,
            inputs=[photo],
            outputs=[preview, scene, status, prompt_box],
        )
        photo.upload(
            fn=analyze_photo,
            inputs=[photo],
            outputs=[preview, scene, status, prompt_box],
        )
        generate_btn.click(
            fn=lambda: gr.update(interactive=False),
            outputs=[generate_btn],
        ).then(
            fn=generate_photo,
            inputs=[photo, costume, scene, steps, max_size, keep_face],
            outputs=[result, status, prompt_box],
        ).then(
            fn=lambda: gr.update(interactive=True),
            outputs=[generate_btn],
        )
        paste_btn.click(
            fn=paste_face_only,
            inputs=[photo, result],
            outputs=[result, status],
        )

        gr.Markdown(
            "Cierra esta ventana y ábrela de nuevo con start-sanjuanero.bat para usar el traje de referencia. "
            "El rostro debe verse nítido y de frente. No pulses Generar dos veces."
        )

    return demo


if __name__ == "__main__":
    ui = get_ui()
    ui.queue(default_concurrency_limit=1)
    ui.launch(
        server_name="127.0.0.1",
        server_port=7861,
        inbrowser=True,
        show_error=True,
        footer_links=[],
        theme=gr.themes.Default(primary_hue="red", secondary_hue="orange"),
        css=CSS,
    )
