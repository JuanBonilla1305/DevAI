"""Generación local de la imagen Sanjuanero usando FastSD + FLUX.2 Klein."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps
from backend.models.lcmdiffusion_setting import DiffusionTask
from backend.utils import get_image_edit_dimensions
from constants import DEVICE
from frontend.utils import is_reshape_required
from frontend.webui.errors import show_error
from models.interface_types import InterfaceType
from sanjuanero.face_preserve import preserve_face
from sanjuanero.prompts import build_prompt
from state import get_context, get_settings

FLUX_KLEIN_MODEL = "rupeshs/flux2-klein-4b-int4-ov"
FEMALE_COSTUME_PATH = (
    Path(__file__).resolve().parent / "referencias" / "traje_mujer.png"
)
# Two reference images roughly double FLUX attention RAM.
DUAL_IMAGE_MAX = 512

_previous_width = 0
_previous_height = 0
_previous_model_id = ""
_previous_num_of_images = 0


def load_costume_reference(scene: str) -> Optional[Image.Image]:
    if scene not in {"Mujer", "Pareja (hombre y mujer)", "Dos mujeres"}:
        return None
    if not FEMALE_COSTUME_PATH.exists():
        return None
    return ImageOps.exif_transpose(Image.open(FEMALE_COSTUME_PATH)).convert("RGB")


def _fit_image(image: Image.Image, max_size: int) -> Image.Image:
    width, height = get_image_edit_dimensions(image, max_size=max_size)
    return image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)


def generate_sanjuanero(
    image: Image.Image,
    scene: str,
    steps: int = 4,
    max_size: int = 768,
    costume: Optional[Image.Image] = None,
    keep_face: bool = True,
) -> tuple[Optional[Image.Image], float, str, bool]:
    global _previous_width, _previous_height, _previous_model_id, _previous_num_of_images

    app_settings = get_settings()
    context = get_context(InterfaceType.WEBUI)
    setting = app_settings.settings.lcm_diffusion_setting

    image = ImageOps.exif_transpose(image).convert("RGB")
    original_for_face = image.copy()
    if costume is not None:
        costume = ImageOps.exif_transpose(costume).convert("RGB")
    else:
        costume = load_costume_reference(scene)
    prompt = build_prompt(scene, has_costume_ref=costume is not None)

    output_max = int(max_size)
    if costume is not None:
        output_max = min(output_max, DUAL_IMAGE_MAX)
        image = _fit_image(image, output_max)
        costume = _fit_image(costume, output_max)
        width, height = costume.size
    else:
        width, height = get_image_edit_dimensions(image, max_size=output_max)

    setting.prompt = prompt
    setting.negative_prompt = ""
    setting.init_image = [image, costume] if costume is not None else image
    setting.diffusion_task = DiffusionTask.edit_image.value
    setting.use_openvino = True
    setting.use_lcm_lora = False
    setting.use_gguf_model = False
    setting.use_tiny_auto_encoder = False
    setting.use_offline_model = False
    setting.openvino_lcm_model_id = FLUX_KLEIN_MODEL
    setting.inference_steps = int(steps)
    setting.image_width = width
    setting.image_height = height
    setting.number_of_images = 1
    setting.guidance_scale = 1.0

    if setting.lora:
        setting.lora.enabled = False
    if setting.controlnet:
        setting.controlnet.enabled = False

    reshape = False
    if setting.use_openvino:
        reshape = is_reshape_required(
            _previous_width,
            width,
            _previous_height,
            height,
            _previous_model_id,
            setting.openvino_lcm_model_id,
            _previous_num_of_images,
            1,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            context.generate_text_to_image,
            app_settings.settings,
            reshape,
            DEVICE,
            False,
        )
        images = future.result()

    if not images:
        show_error(context.error or "No se pudo generar la imagen.")
        return None, context.latency, prompt, False

    result = images[0]
    face_ok = False
    if keep_face:
        result, face_ok = preserve_face(original_for_face, result)
        images = [result]

    context.save_images(images, app_settings.settings)

    _previous_width = width
    _previous_height = height
    _previous_model_id = setting.openvino_lcm_model_id
    _previous_num_of_images = 1
    return result, context.latency, prompt, face_ok
