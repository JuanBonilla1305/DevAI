"""Intercambia el rostro real sobre el baile. Sin recortes ovalados."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

MODELS_DIR = Path(__file__).resolve().parent / "models"
INSWAPPER_CANDIDATES = [
    MODELS_DIR / "inswapper_128.onnx",
    Path.home() / ".insightface" / "models" / "inswapper_128.onnx",
]
BUFFALO_DIR = Path.home() / ".insightface" / "models" / "buffalo_l"

_app = None
_swapper = None


def _inswapper_path() -> Path | None:
    for path in INSWAPPER_CANDIDATES:
        if path.exists() and path.stat().st_size > 1_000_000:
            return path
    return None


def _buffalo_ready() -> bool:
    if not BUFFALO_DIR.exists():
        return False
    needed = ["det_10g.onnx", "w600k_r50.onnx", "2d106det.onnx"]
    return all((BUFFALO_DIR / name).exists() for name in needed)


def _get_swapper():
    global _app, _swapper
    if _app is not None and _swapper is not None:
        return _app, _swapper

    model_path = _inswapper_path()
    if model_path is None or not _buffalo_ready():
        return None, None

    from insightface.app import FaceAnalysis
    from insightface.model_zoo import get_model

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    swapper = get_model(str(model_path), download=False, download_zip=False)
    _app, _swapper = app, swapper
    return _app, _swapper


# Limites para decidir que caras de la imagen generada son validas.
#
# Los valores originales asumen una escena de baile de cuerpo entero: la
# cabeza sale pequenia y en la parte alta del encuadre. En un retrato de busto
# la cara ocupa mas de la mitad del ancho y queda centrada, asi que esos
# limites la rechazaban siempre y el intercambio se saltaba en silencio.
#
# Se dejan los valores del proyecto original por defecto y se ajustan con
# variables de entorno desde el tema que los necesite.
CENTRO_Y_MAXIMO = float(os.environ.get("CARA_CENTRO_Y_MAX", "0.55"))
ANCHO_MINIMO = float(os.environ.get("CARA_ANCHO_MIN", "0.03"))
ANCHO_MAXIMO = float(os.environ.get("CARA_ANCHO_MAX", "0.55"))


def _pick_dest_faces(faces, width: int, height: int, count: int):
    scored = []
    for face in faces:
        x1, y1, x2, y2 = [float(v) for v in face.bbox]
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        if cy > height * CENTRO_Y_MAXIMO:
            continue
        box_w = max(1.0, x2 - x1)
        if box_w / width < ANCHO_MINIMO or box_w / width > ANCHO_MAXIMO:
            continue
        score = (1.0 - abs(cx / width - 0.52)) + (1.0 - cy / height)
        scored.append((score, face))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [face for _, face in scored[:count]]
    return sorted(
        selected,
        key=lambda face: float((face.bbox[0] + face.bbox[2]) / 2.0),
    )


def _head_crop_box(bbox, width: int, height: int, scale: float = 2.6):
    x1, y1, x2, y2 = [float(v) for v in bbox]
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bw = max(8.0, (x2 - x1) * scale)
    bh = max(8.0, (y2 - y1) * scale)
    nx1 = max(0, int(cx - bw / 2.0))
    ny1 = max(0, int(cy - bh / 2.0))
    nx2 = min(width, int(cx + bw / 2.0))
    ny2 = min(height, int(cy + bh / 2.0))
    if nx2 - nx1 < 16 or ny2 - ny1 < 16:
        return None
    return nx1, ny1, nx2, ny2


def _largest_face(faces):
    return max(
        faces,
        key=lambda face: float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])),
    )


def _swap_on_image(app, swapper, source_face, image):
    faces = app.get(image)
    if not faces:
        return image, None, False
    dest_face = _largest_face(faces)
    swapped = swapper.get(image, dest_face, source_face, paste_back=True)

    # Un segundo pase refuerza la identidad cuando la cara final ocupa pocos
    # píxeles dentro de una composición de cuerpo completo.
    refined_faces = app.get(swapped)
    if refined_faces:
        refined_face = _largest_face(refined_faces)
        swapped = swapper.get(
            swapped,
            refined_face,
            source_face,
            paste_back=True,
        )

    return swapped, dest_face, True


def _face_region_mask(height: int, width: int, face, expand: float = 1.55) -> np.ndarray:
    x1, y1, x2, y2 = [float(v) for v in face.bbox]
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bw = max(8.0, (x2 - x1) * expand / 2.0)
    bh = max(8.0, (y2 - y1) * expand / 2.0)
    mask = np.zeros((height, width), np.float32)
    cv2.ellipse(
        mask,
        (int(cx), int(cy)),
        (int(bw), int(bh)),
        0,
        0,
        360,
        1.0,
        -1,
    )
    return cv2.GaussianBlur(mask, (51, 51), 0)


def _blend_swapped_face(base, swapped, face, strength: float):
    strength = float(max(0.0, min(1.0, strength)))
    mask = _face_region_mask(base.shape[0], base.shape[1], face)[:, :, None] * strength
    mixed = base.astype(np.float32) * (1.0 - mask) + swapped.astype(np.float32) * mask
    return np.clip(mixed, 0, 255).astype(np.uint8)


def _swap_one_face(app, swapper, source_face, dest, dest_face, identity_strength):
    dest_h, dest_w = dest.shape[:2]
    box = _head_crop_box(dest_face.bbox, dest_w, dest_h)
    if box is not None:
        x1, y1, x2, y2 = box
        crop = dest[y1:y2, x1:x2]
        ch, cw = crop.shape[:2]
        target = 640
        scale = target / float(max(ch, cw))
        if scale > 1.05:
            new_w = max(64, int(round(cw * scale)))
            new_h = max(64, int(round(ch * scale)))
            crop_up = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        else:
            crop_up = crop

        swapped_up, crop_face, ok = _swap_on_image(
            app,
            swapper,
            source_face,
            crop_up,
        )
        if ok and crop_face is not None:
            blurred = cv2.GaussianBlur(swapped_up, (0, 0), 1.0)
            swapped_up = cv2.addWeighted(
                swapped_up,
                1.18,
                blurred,
                -0.18,
                0,
            )
            crop_mixed = _blend_swapped_face(
                crop_up,
                swapped_up,
                crop_face,
                identity_strength,
            )
            swapped_crop = cv2.resize(crop_mixed, (cw, ch), interpolation=cv2.INTER_AREA)
            result = dest.copy()
            result[y1:y2, x1:x2] = swapped_crop
            return result, True

    raw_swap = swapper.get(dest, dest_face, source_face, paste_back=True)
    return (
        _blend_swapped_face(dest, raw_swap, dest_face, identity_strength),
        True,
    )


def _match_faces(source_faces, dest_faces):
    remaining = list(source_faces)
    matches = []
    for dest_face in dest_faces:
        dest_gender = int(getattr(dest_face, "gender", -1))
        dest_age = int(getattr(dest_face, "age", 0) or 0)

        def match_score(source_face):
            source_gender = int(getattr(source_face, "gender", -1))
            source_age = int(getattr(source_face, "age", 0) or 0)
            gender_penalty = 10.0 if (
                dest_gender >= 0
                and source_gender >= 0
                and dest_gender != source_gender
            ) else 0.0
            return gender_penalty + abs(source_age - dest_age) / 100.0

        source_index = min(
            range(len(remaining)),
            key=lambda index: match_score(remaining[index]),
        )
        source_face = remaining.pop(source_index)
        matches.append((source_face, dest_face))
    return matches


def preserve_face(
    original: Image.Image,
    generated: Image.Image,
    identity_strength: float = 0.75,
    max_faces: int = 1,
) -> tuple[Image.Image, bool]:
    """Pone la cara real sobre el baile con InsightFace, no con un recorte."""
    identity_strength = float(max(0.35, min(1.0, identity_strength)))
    app, swapper = _get_swapper()
    if app is None or swapper is None:
        print("Sin modelo de intercambio; no se pega recorte sobre el baile.")
        return generated, False

    source = cv2.cvtColor(np.array(original.convert("RGB")), cv2.COLOR_RGB2BGR)

    generated_rgb = generated.convert("RGB")
    if max(generated_rgb.size) <= 512:
        generated_rgb = generated_rgb.resize(
            (generated_rgb.width * 2, generated_rgb.height * 2),
            Image.Resampling.LANCZOS,
        )
    dest = cv2.cvtColor(np.array(generated_rgb), cv2.COLOR_RGB2BGR)
    source_faces = app.get(source)
    dest_faces = app.get(dest)
    if not source_faces or not dest_faces:
        print("No se detectaron caras para el intercambio.")
        return generated, False

    max_faces = max(1, min(2, int(max_faces)))
    ranked_source_faces = sorted(
        source_faces,
        key=lambda face: float(
            (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        ),
        reverse=True,
    )
    largest_source_area = float(
        (ranked_source_faces[0].bbox[2] - ranked_source_faces[0].bbox[0])
        * (ranked_source_faces[0].bbox[3] - ranked_source_faces[0].bbox[1])
    )
    selected_source_faces = [
        face
        for face in ranked_source_faces
        if float(
            (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        ) >= largest_source_area * 0.18
    ][:max_faces]
    selected_source_faces.sort(
        key=lambda face: float((face.bbox[0] + face.bbox[2]) / 2.0)
    )

    dest_h, dest_w = dest.shape[:2]
    selected_dest_faces = _pick_dest_faces(
        dest_faces,
        dest_w,
        dest_h,
        len(selected_source_faces),
    )
    if len(selected_dest_faces) < len(selected_source_faces):
        print("No hay suficientes caras de baile fiables para el intercambio.")
        return generated, False

    swapped = dest
    swapped_count = 0
    for source_face, dest_face in _match_faces(
        selected_source_faces,
        selected_dest_faces,
    ):
        swapped, ok = _swap_one_face(
            app,
            swapper,
            source_face,
            swapped,
            dest_face,
            identity_strength,
        )
        if ok:
            swapped_count += 1

    if swapped_count == 0:
        return generated, False

    print(
        f"{swapped_count} rostro(s) intercambiado(s) con InsightFace "
        f"(identidad {identity_strength:.2f})."
    )
    rgb = cv2.cvtColor(swapped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb), swapped_count == len(selected_source_faces)
