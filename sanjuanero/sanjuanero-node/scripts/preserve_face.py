"""Pega el rostro de la foto original sobre el resultado de FastSD."""

import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2] / "fastsdcpu-main"
sys.path.insert(0, str(ROOT))

from sanjuanero.face_preserve import preserve_face


def main() -> int:
    if len(sys.argv) not in (4, 5, 6):
        print(
            "Uso: preserve_face.py original resultado salida "
            "[identidad_0_a_1] [cantidad_rostros]"
        )
        return 1

    original = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB")
    generated = ImageOps.exif_transpose(Image.open(sys.argv[2])).convert("RGB")
    identity_strength = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.75
    max_faces = int(sys.argv[5]) if len(sys.argv) >= 6 else 1
    result, ok = preserve_face(original, generated, identity_strength, max_faces)
    result.save(sys.argv[3], quality=95)
    print("OK" if ok else "SKIP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
