"""Recorta un primer plano del rostro para bloquear la identidad."""

import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2] / "fastsdcpu-main"
sys.path.insert(0, str(ROOT))

from sanjuanero.detect import _clamp_box, largest_face_box


def crop_identity(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    box = largest_face_box(image)
    if box is None:
        return image

    x1, y1, x2, y2 = box
    box_w, box_h = x2 - x1, y2 - y1
    crop_box = _clamp_box(
        x1 - int(box_w * 0.55),
        y1 - int(box_h * 0.90),
        x2 + int(box_w * 0.55),
        y2 + int(box_h * 0.50),
        width,
        height,
    )
    return image.crop(crop_box)


def main() -> int:
    if len(sys.argv) != 3:
        print("Uso: crop_face.py original salida")
        return 1

    original = Image.open(sys.argv[1])
    crop_identity(original).save(sys.argv[2], quality=95)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
