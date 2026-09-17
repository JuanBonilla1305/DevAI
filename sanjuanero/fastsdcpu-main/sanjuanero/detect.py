"""Detección local de rostros y género para Sanjuanero IA."""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

MODELS_DIR = Path(__file__).resolve().parent / "models"
GENDER_PROTO = MODELS_DIR / "gender_deploy.prototxt"
GENDER_MODEL = MODELS_DIR / "gender_net.caffemodel"
GENDER_MODEL_URLS = [
    "https://github.com/smahesh29/Gender-and-Age-Detection/raw/master/gender_net.caffemodel",
    "https://media.githubusercontent.com/media/smahesh29/Gender-and-Age-Detection/master/gender_net.caffemodel",
    "https://www.dropbox.com/s/iyv483wz7ztr9gh/gender_net.caffemodel?dl=1",
]
GENDER_LABELS = ("hombre", "mujer")
MODEL_MEAN = (78.4263377603, 87.7689143744, 114.895847746)
SCENE_CHOICES = [
    "Mujer",
    "Hombre",
    "Pareja (hombre y mujer)",
    "Dos mujeres",
    "Dos hombres",
]

_gender_net = None


@dataclass
class Person:
    gender: str
    confidence: float
    box: tuple[int, int, int, int]


@dataclass
class DetectionResult:
    people: list[Person]
    scene: str
    annotated: Image.Image
    message: str


def _ensure_gender_model() -> bool:
    if GENDER_MODEL.exists() and GENDER_MODEL.stat().st_size > 1_000_000:
        return True
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    urllib.request.install_opener(opener)
    for url in GENDER_MODEL_URLS:
        try:
            print(f"Descargando clasificador de género desde {url}")
            urllib.request.urlretrieve(url, GENDER_MODEL)
            if GENDER_MODEL.exists() and GENDER_MODEL.stat().st_size > 1_000_000:
                return True
        except Exception as exc:
            print(f"No se pudo descargar el modelo de género: {exc}")
    return GENDER_MODEL.exists() and GENDER_MODEL.stat().st_size > 1_000_000


def _get_gender_net():
    global _gender_net
    if _gender_net is not None:
        return _gender_net
    if not GENDER_PROTO.exists() or not _ensure_gender_model():
        return None
    _gender_net = cv2.dnn.readNetFromCaffe(str(GENDER_PROTO), str(GENDER_MODEL))
    return _gender_net


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _detect_faces_mediapipe(bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    try:
        import mediapipe as mp
    except Exception:
        return []

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    height, width = bgr.shape[:2]
    boxes: list[tuple[int, int, int, int]] = []
    for model_selection in (0, 1):
        detector = mp.solutions.face_detection.FaceDetection(
            model_selection=model_selection,
            min_detection_confidence=0.4,
        )
        try:
            result = detector.process(rgb)
        finally:
            detector.close()
        if not result.detections:
            continue
        for detection in result.detections:
            bbox = detection.location_data.relative_bounding_box
            x1 = int(bbox.xmin * width)
            y1 = int(bbox.ymin * height)
            x2 = int((bbox.xmin + bbox.width) * width)
            y2 = int((bbox.ymin + bbox.height) * height)
            boxes.append(_clamp_box(x1, y1, x2, y2, width, height))
    return boxes


def _filter_tiny_faces(
    boxes: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    if not boxes:
        return []
    areas = [(box[2] - box[0]) * (box[3] - box[1]) for box in boxes]
    largest = max(areas)
    minimum = max(largest * 0.4, int(width * height * 0.015))
    return [box for box, area in zip(boxes, areas) if area >= minimum]


def _detect_faces_haar(bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(str(cascade_path))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(48, 48))
    boxes = []
    height, width = bgr.shape[:2]
    for x, y, w, h in faces:
        boxes.append(_clamp_box(x, y, x + w, y + h, width, height))
    return boxes


def _clamp_box(
    x1: int, y1: int, x2: int, y2: int, width: int, height: int
) -> tuple[int, int, int, int]:
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width, x2))
    y2 = max(y1 + 1, min(height, y2))
    return x1, y1, x2, y2


def _expand_box(
    box: tuple[int, int, int, int],
    width: int,
    height: int,
    margin: float = 0.25,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    dx, dy = int(bw * margin), int(bh * margin)
    return _clamp_box(x1 - dx, y1 - dy, x2 + dx, y2 + dy, width, height)


def _classify_gender(bgr: np.ndarray, box: tuple[int, int, int, int]) -> tuple[str, float]:
    net = _get_gender_net()
    if net is None:
        return "mujer", 0.0

    x1, y1, x2, y2 = box
    face = bgr[y1:y2, x1:x2]
    if face.size == 0:
        return "mujer", 0.0

    blob = cv2.dnn.blobFromImage(face, 1.0, (227, 227), MODEL_MEAN, swapRB=False)
    net.setInput(blob)
    preds = net.forward()[0]
    idx = int(np.argmax(preds))
    return GENDER_LABELS[idx], float(preds[idx])


def _box_iou(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return inter / float(area_a + area_b - inter)


def _merge_overlapping_boxes(
    boxes: list[tuple[int, int, int, int]],
    iou_threshold: float = 0.35,
) -> list[tuple[int, int, int, int]]:
    if len(boxes) <= 1:
        return boxes
    ranked = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    kept: list[tuple[int, int, int, int]] = []
    for box in ranked:
        if any(_box_iou(box, existing) >= iou_threshold for existing in kept):
            continue
        kept.append(box)
    return kept


def _pick_largest(boxes: list[tuple[int, int, int, int]], limit: int = 2) -> list[tuple[int, int, int, int]]:
    ranked = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    selected = ranked[:limit]
    return sorted(selected, key=lambda b: b[0])


def scene_from_people(people: list[Person]) -> str:
    genders = [person.gender for person in people]
    if len(genders) == 0:
        return "Mujer"
    if len(genders) == 1:
        return "Mujer" if genders[0] == "mujer" else "Hombre"
    women = genders.count("mujer")
    men = genders.count("hombre")
    if women == 2:
        return "Dos mujeres"
    if men == 2:
        return "Dos hombres"
    return "Pareja (hombre y mujer)"


def _annotate(image: Image.Image, people: list[Person]) -> Image.Image:
    annotated = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()

    colors = {"mujer": (196, 30, 58), "hombre": (12, 92, 61)}
    for index, person in enumerate(people, start=1):
        x1, y1, x2, y2 = person.box
        color = colors.get(person.gender, (30, 30, 30))
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        label = f"{index}. {person.gender.capitalize()} {person.confidence * 100:.0f}%"
        text_box = draw.textbbox((x1, max(0, y1 - 28)), label, font=font)
        draw.rectangle(text_box, fill=color)
        draw.text((x1, max(0, y1 - 28)), label, fill="white", font=font)
    return annotated


def largest_face_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    image = ImageOps.exif_transpose(image).convert("RGB")
    bgr = _pil_to_bgr(image)
    height, width = bgr.shape[:2]
    boxes = _detect_faces_mediapipe(bgr)
    if not boxes:
        boxes = _detect_faces_haar(bgr)
    boxes = _merge_overlapping_boxes(boxes)
    boxes = _pick_largest(boxes, limit=1)
    if not boxes:
        return None
    return boxes[0]


def detect_people(image: Image.Image) -> DetectionResult:
    image = ImageOps.exif_transpose(image).convert("RGB")
    bgr = _pil_to_bgr(image)
    height, width = bgr.shape[:2]

    boxes = _detect_faces_mediapipe(bgr)
    if not boxes:
        boxes = _detect_faces_haar(bgr)
    boxes = _merge_overlapping_boxes(boxes)
    boxes = _filter_tiny_faces(boxes, width, height)
    boxes = _pick_largest(boxes, limit=2)

    people: list[Person] = []
    for box in boxes:
        crop = _expand_box(box, width, height)
        gender, confidence = _classify_gender(bgr, crop)
        people.append(Person(gender=gender, confidence=confidence, box=box))

    scene = scene_from_people(people)
    annotated = _annotate(image, people)

    if not people:
        message = (
            "No pude detectar rostros con claridad. "
            "Elige si es hombre, mujer o pareja y genera de todas formas."
        )
    elif len(people) == 1:
        person = people[0]
        message = (
            f"Detecté 1 persona: {person.gender} "
            f"({person.confidence * 100:.0f}% de confianza). "
            "Si está mal, corrígelo antes de generar."
        )
    else:
        left, right = people
        message = (
            f"Detecté 2 personas. Izquierda: {left.gender} "
            f"({left.confidence * 100:.0f}%). Derecha: {right.gender} "
            f"({right.confidence * 100:.0f}%). "
            "Si algún género está mal, corrígelo antes de generar."
        )

    return DetectionResult(
        people=people,
        scene=scene,
        annotated=annotated,
        message=message,
    )


def normalize_scene(scene: Optional[str]) -> str:
    if scene in SCENE_CHOICES:
        return scene
    return "Mujer"
