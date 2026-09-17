"""Captura desde la webcam y analisis basico de calidad de la foto."""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

import config

_CLASIFICADOR = None


def _clasificador() -> cv2.CascadeClassifier:
    """Detector de caras Haar que viene incluido con opencv-python."""
    global _CLASIFICADOR
    if _CLASIFICADOR is None:
        ruta = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        _CLASIFICADOR = cv2.CascadeClassifier(str(ruta))
    return _CLASIFICADOR


def detectar_caras(imagen: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Busca caras frontales. Devuelve una lista de (x, y, ancho, alto).

    El tamanio minimo se calcula a partir de la imagen: un minimo fijo en
    pixeles descarta caras validas en fotos pequenias y acepta ruido en las
    grandes. Si con los ajustes estrictos no sale nada, se reintenta con otros
    mas permisivos antes de darse por vencido.
    """
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.equalizeHist(gris)

    lado_menor = min(imagen.shape[:2])
    minimo = max(24, lado_menor // 8)

    intentos = (
        (1.15, 6, minimo),
        (1.10, 5, max(20, minimo // 2)),
        (1.05, 3, max(16, minimo // 4)),
    )

    for escala, vecinos, tamanio in intentos:
        caras = _clasificador().detectMultiScale(
            gris, scaleFactor=escala, minNeighbors=vecinos,
            minSize=(tamanio, tamanio)
        )
        if len(caras):
            return [tuple(int(v) for v in c) for c in caras]

    return []


def analizar(imagen: np.ndarray) -> dict:
    """Metricas objetivas para que el agente decida si la foto sirve."""
    alto, ancho = imagen.shape[:2]
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    caras = detectar_caras(imagen)

    nitidez = float(cv2.Laplacian(gris, cv2.CV_64F).var())
    brillo = float(gris.mean())

    info: dict = {
        "ancho": ancho,
        "alto": alto,
        "caras_detectadas": len(caras),
        "nitidez": round(nitidez, 1),
        "brillo": round(brillo, 1),
        "problemas": [],
    }

    if caras:
        x, y, w, h = max(caras, key=lambda c: c[2] * c[3])
        info["cara_principal"] = {"x": x, "y": y, "ancho": w, "alto": h}
        info["porcentaje_cara"] = round(100 * (w * h) / (ancho * alto), 1)
        cx, cy = x + w / 2, y + h / 2
        info["desvio_centro_pct"] = round(
            100 * max(abs(cx - ancho / 2) / ancho, abs(cy - alto / 2) / alto), 1
        )
    else:
        info["porcentaje_cara"] = 0.0

    p = info["problemas"]
    if not caras:
        p.append("no se detecto ninguna cara")
    if len(caras) > 1:
        p.append(f"hay {len(caras)} caras, el retrato deberia tener una sola")
    if nitidez < 60:
        p.append("imagen movida o desenfocada")
    if brillo < 55:
        p.append("foto muy oscura")
    if brillo > 205:
        p.append("foto quemada por exceso de luz")
    if caras and info["porcentaje_cara"] < 4:
        p.append("la cara queda muy lejos, conviene acercarse")

    info["apta"] = not p
    return info


def _dibujar_ayuda(marco: np.ndarray, caras: list, congelado: bool) -> np.ndarray:
    vista = marco.copy()
    for (x, y, w, h) in caras:
        cv2.rectangle(vista, (x, y), (x + w, y + h), (0, 220, 255), 2)

    alto, ancho = vista.shape[:2]
    cv2.rectangle(vista, (0, alto - 46), (ancho, alto), (0, 0, 0), -1)
    texto = (
        "Guardando..." if congelado
        else "ESPACIO = tomar foto   |   R = reintentar   |   ESC = cancelar"
    )
    cv2.putText(vista, texto, (14, alto - 16), cv2.FONT_HERSHEY_SIMPLEX,
                0.62, (255, 255, 255), 1, cv2.LINE_AA)

    estado = f"caras: {len(caras)}"
    color = (0, 220, 0) if len(caras) == 1 else (0, 140, 255)
    cv2.putText(vista, estado, (14, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, color, 2, cv2.LINE_AA)
    return vista


def capturar(titulo: str = "camara80s - retrato") -> Path | None:
    """Abre la ventana de la webcam. Devuelve la ruta de la foto o None."""
    captura = cv2.VideoCapture(config.INDICE_CAMARA, cv2.CAP_DSHOW)
    if not captura.isOpened():
        captura = cv2.VideoCapture(config.INDICE_CAMARA)
    if not captura.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la camara {config.INDICE_CAMARA}. "
            "Cierra Teams/Zoom/Meet o cambia INDICE_CAMARA en el .env."
        )

    captura.set(cv2.CAP_PROP_FRAME_WIDTH, config.ANCHO_CAMARA)
    captura.set(cv2.CAP_PROP_FRAME_HEIGHT, config.ALTO_CAMARA)

    cv2.namedWindow(titulo, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(titulo, 960, 540)

    ruta: Path | None = None
    caras: list = []
    cuadro = 0
    try:
        while True:
            ok, marco = captura.read()
            if not ok:
                break
            marco = cv2.flip(marco, 1)  # efecto espejo, mas natural

            # Detectar cada 5 cuadros: el Haar es caro para 30 fps.
            if cuadro % 5 == 0:
                caras = detectar_caras(marco)
            cuadro += 1

            cv2.imshow(titulo, _dibujar_ayuda(marco, caras, False))
            tecla = cv2.waitKey(1) & 0xFF

            if tecla == 27:  # ESC
                break
            if tecla == 32:  # ESPACIO
                nombre = f"captura_{time.strftime('%Y%m%d_%H%M%S')}.png"
                ruta = config.CAPTURAS / nombre
                cv2.imwrite(str(ruta), marco)
                cv2.imshow(titulo, _dibujar_ayuda(marco, caras, True))
                cv2.waitKey(450)
                break

            if cv2.getWindowProperty(titulo, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        captura.release()
        cv2.destroyAllWindows()
        for _ in range(4):
            cv2.waitKey(1)

    return ruta
