"""Extrae de la foto subida una referencia de rostro y cabello para FLUX."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

MODELS_DIR = Path.home() / ".insightface" / "models" / "buffalo_l"


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("Uso: extract_head_reference.py entrada salida_1 [salida_2]")
        return 1

    image = cv2.imread(sys.argv[1])
    if image is None:
        print("No se pudo leer la fotografía.")
        return 1

    from insightface.app import FaceAnalysis

    app = FaceAnalysis(
        name="buffalo_l",
        root=str(MODELS_DIR.parents[1]),
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=(640, 640))
    faces = app.get(image)
    if not faces:
        print("No se detectó un rostro.")
        return 1

    ranked_faces = sorted(
        faces,
        key=lambda item: float(
            (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1])
        ),
        reverse=True,
    )
    requested = len(sys.argv) - 2
    largest_area = float(
        (ranked_faces[0].bbox[2] - ranked_faces[0].bbox[0])
        * (ranked_faces[0].bbox[3] - ranked_faces[0].bbox[1])
    )
    selected_faces = [
        face
        for face in ranked_faces
        if float(
            (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        ) >= largest_area * 0.18
    ][:requested]

    if len(selected_faces) < requested:
        print(f"Solo se detectaron {len(selected_faces)} rostros principales.")
        return 1

    if requested == 2:
        selected_faces.sort(
            key=lambda face: float((face.bbox[0] + face.bbox[2]) / 2.0)
        )

    height, width = image.shape[:2]
    separation_x = None
    if requested == 2:
        centers = [
            float((face.bbox[0] + face.bbox[2]) / 2.0)
            for face in selected_faces
        ]
        separation_x = int(sum(centers) / 2.0)

    for index, (face, output_path) in enumerate(
        zip(selected_faces, sys.argv[2:])
    ):
        x1, y1, x2, y2 = [float(value) for value in face.bbox]
        face_w = max(1.0, x2 - x1)
        face_h = max(1.0, y2 - y1)
        center_x = (x1 + x2) / 2.0

        crop_x1 = max(0, int(center_x - face_w * 1.45))
        crop_x2 = min(width, int(center_x + face_w * 1.45))
        if separation_x is not None:
            if index == 0:
                crop_x2 = min(crop_x2, separation_x)
            else:
                crop_x1 = max(crop_x1, separation_x)
        crop_y1 = max(0, int(y1 - face_h * 1.30))
        crop_y2 = min(height, int(y2 + face_h * 1.80))
        crop = image[crop_y1:crop_y2, crop_x1:crop_x2]

        if crop.size == 0 or min(crop.shape[:2]) < 32:
            print("El recorte de cabeza no es válido.")
            return 1

        if not cv2.imwrite(output_path, crop, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            print("No se pudo guardar la referencia.")
            return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
