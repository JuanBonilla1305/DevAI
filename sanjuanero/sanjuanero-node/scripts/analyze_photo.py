"""Detecta localmente cada rostro, género aparente y grupo de edad."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

MODELS_DIR = Path.home() / ".insightface" / "models" / "buffalo_l"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENDER_MODELS_DIR = (
    PROJECT_ROOT / "fastsdcpu-main" / "sanjuanero" / "models"
)
FACE_ATTRIB_MODEL = (
    GENDER_MODELS_DIR
    / "face_attrib_net"
    / "face_attrib_net-onnx-float"
    / "face_attrib_net.onnx"
)


def detect_eyewear(session, image, bbox) -> tuple[bool, str | None, float]:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    image_h, image_w = image.shape[:2]
    margin_x = width * 0.20
    margin_y = height * 0.20
    crop = image[
        max(0, int(y1 - margin_y)):min(image_h, int(y2 + margin_y)),
        max(0, int(x1 - margin_x)):min(image_w, int(x2 + margin_x)),
    ]
    if crop.size == 0:
        return False, None, 0.0

    target = 128
    scale = min(target / crop.shape[1], target / crop.shape[0])
    resized = cv2.resize(
        crop,
        (
            max(1, int(round(crop.shape[1] * scale))),
            max(1, int(round(crop.shape[0] * scale))),
        ),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.zeros((target, target, 3), dtype=np.uint8)
    offset_x = (target - resized.shape[1]) // 2
    offset_y = (target - resized.shape[0]) // 2
    canvas[
        offset_y:offset_y + resized.shape[0],
        offset_x:offset_x + resized.shape[1],
    ] = resized
    tensor = (
        cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        .transpose(2, 0, 1)[None]
        .astype(np.float32)
        / 255.0
    )
    probabilities = np.asarray(
        session.run(None, {"image": tensor})[0]
    ).reshape(-1)
    glasses_score = float(probabilities[2])
    sunglasses_score = float(probabilities[4])
    if sunglasses_score >= 0.50:
        return True, "gafas de sol", sunglasses_score
    if glasses_score >= 0.50:
        return True, "gafas", glasses_score
    return False, None, max(glasses_score, sunglasses_score)


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "Falta la fotografía."}))
        return 1

    image = cv2.imread(sys.argv[1])
    if image is None:
        print(json.dumps({"ok": False, "error": "No se pudo leer la fotografía."}))
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
        print(json.dumps({
            "ok": True,
            "faceCount": 0,
            "costume": None,
            "message": "No se detectó un rostro con suficiente claridad.",
        }))
        return 0

    largest_area = max(
        float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))
        for face in faces
    )
    relevant_faces = [
        face
        for face in faces
        if float(
            (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        ) >= largest_area * 0.18
    ]
    relevant_faces = sorted(
        relevant_faces,
        key=lambda face: float(
            (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        ),
        reverse=True,
    )[:2]

    image_height, image_width = image.shape[:2]
    gender_net = cv2.dnn.readNet(
        str(GENDER_MODELS_DIR / "gender_net.caffemodel"),
        str(GENDER_MODELS_DIR / "gender_deploy.prototxt"),
    )
    eyewear_session = (
        ort.InferenceSession(
            str(FACE_ATTRIB_MODEL),
            providers=["CPUExecutionProvider"],
        )
        if FACE_ATTRIB_MODEL.exists()
        else None
    )

    ordered_faces = sorted(
        relevant_faces,
        key=lambda face: float((face.bbox[0] + face.bbox[2]) / 2.0),
    )
    detected_people = []

    for index, face in enumerate(ordered_faces):
        x1, y1, x2, y2 = [int(value) for value in face.bbox]
        padding = int(max(1, x2 - x1) * 0.20)
        face_crop = image[
            max(0, y1 - padding):min(image_height, y2 + padding),
            max(0, x1 - padding):min(image_width, x2 + padding),
        ]

        gender = "hombre" if int(getattr(face, "gender", 1)) == 1 else "mujer"
        confidence = None
        if face_crop.size:
            blob = cv2.dnn.blobFromImage(
                face_crop,
                1.0,
                (227, 227),
                (78.4263377603, 87.7689143744, 114.895847746),
                swapRB=False,
            )
            gender_net.setInput(blob)
            scores = gender_net.forward()[0]
            gender_index = int(scores.argmax())
            gender = "hombre" if gender_index == 0 else "mujer"
            confidence = round(float(scores[gender_index]), 3)

        estimated_age = int(getattr(face, "age", 0) or 0)
        has_glasses = False
        glasses_type = None
        glasses_confidence = None
        if eyewear_session is not None:
            (
                has_glasses,
                glasses_type,
                glasses_confidence,
            ) = detect_eyewear(eyewear_session, image, face.bbox)
        if estimated_age < 13:
            age_group = "niño"
            label = "niño" if gender == "hombre" else "niña"
        elif estimated_age < 18:
            age_group = "adolescente"
            label = "adolescente hombre" if gender == "hombre" else "adolescente mujer"
        else:
            age_group = "adulto"
            label = gender

        detected_people.append({
            "index": index + 1,
            "gender": gender,
            "genderConfidence": confidence,
            "estimatedAge": estimated_age,
            "ageGroup": age_group,
            "label": label,
            "hasGlasses": has_glasses,
            "glassesType": glasses_type,
            "glassesConfidence": (
                round(glasses_confidence, 3)
                if glasses_confidence is not None
                else None
            ),
            "bbox": [x1, y1, x2, y2],
        })

    primary = max(
        detected_people,
        key=lambda person: (
            person["bbox"][2] - person["bbox"][0]
        ) * (
            person["bbox"][3] - person["bbox"][1]
        ),
    )
    costume = primary["gender"]

    print(json.dumps({
        "ok": True,
        "faceCount": len(relevant_faces),
        "detectedFaceCount": len(faces),
        "peopleCount": "2" if len(relevant_faces) >= 2 else "1",
        "costume": costume,
        "genderConfidence": primary["genderConfidence"],
        "people": detected_people,
        "composition": [person["label"] for person in detected_people],
        "message": "Selección automática realizada.",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
