#!/usr/bin/env python3
"""Hornea la capa RETRO en dos láminas para no disparar el límite de 30 req/s.

La UI React posicionaba 12 PNG sueltos con CSS (porcentajes sobre 1672x940,
object-fit: contain, rotate y opacity). Ese burst de peticiones hacía que el
rate limiter de Flask devolviera 429 y algunos stickers no aparecieran.

Este script aplica la misma geometría con PIL y deja dos imágenes:
  - retro_static.png: 10 recortes decorativos.
  - retro_signal.png: REC + ON AIR (su opacidad sigue a `is-live`).

Si cambias posiciones/rotaciones en styles.css, actualiza ITEMS y vuelve a
ejecutar este script. No toca backend ni datos de la radio.
"""

from pathlib import Path

from PIL import Image

ARTBOARD = (1672, 940)
ASSETS = Path(__file__).resolve().parents[1] / "public" / "assets" / "radio-ui"

# (archivo, left%, top%, width%, height%, rotate_deg, opacity)
STATIC = [
    ("texture_halftone_overlay.png", 0.0, 0.0, 100.0, 100.0, 0, 0.06),
    ("sticker_canal_24.png", 0.6, 1.2, 15.5, 4.2, -2, 0.85),
    ("tape_en_vivo.png", 20.2, 1.4, 13.5, 3.4, 1.5, 0.8),
    ("tape_canal_24_mix.png", 19.2, 16.2, 19.5, 3.1, -1, 0.75),
    ("tape_request_line.png", 19.2, 59.6, 19.5, 2.2, 0.8, 0.7),
    ("graphic_eye_collage.png", 1.2, 53.5, 15.6, 5.2, -3, 0.35),
    ("sticker_stay_tuned.png", 1.0, 82.6, 15.8, 5.4, 2, 0.7),
    ("banner_top_10.png", 59.2, 13.2, 17.5, 3.6, -1.5, 0.8),
    ("emblem_target_crosshair.png", 89.0, 59.2, 7.0, 5.5, -6, 0.22),
    ("emblem_ia_radio.png", 55.6, 62.6, 2.6, 4.2, 4, 0.45),
]
SIGNAL = [
    ("badge_rec_dot.png", 30.6, 45.6, 3.2, 2.4, 0, 0.9),
    ("sticker_on_air.png", 76.5, 2.6, 8.5, 7.5, 3, 0.85),
]


def with_opacity(image, opacity):
    if opacity >= 1:
        return image
    result = image.copy()
    alpha = result.getchannel("A").point(lambda value: round(value * opacity))
    result.putalpha(alpha)
    return result


def place(canvas, item):
    name, left, top, width, height, rotation, opacity = item
    source = Image.open(ASSETS / name).convert("RGBA")
    box_w = ARTBOARD[0] * width / 100
    box_h = ARTBOARD[1] * height / 100
    scale = min(box_w / source.width, box_h / source.height)  # object-fit: contain
    size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    source = source.resize(size, Image.Resampling.LANCZOS)

    if rotation:
        # CSS gira en sentido horario; PIL en antihorario.
        source = source.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)

    source = with_opacity(source, opacity)
    cx = ARTBOARD[0] * (left + width / 2) / 100
    cy = ARTBOARD[1] * (top + height / 2) / 100
    x = round(cx - source.width / 2)
    y = round(cy - source.height / 2)
    canvas.alpha_composite(source, (x, y))


def build(items, filename):
    canvas = Image.new("RGBA", ARTBOARD, (0, 0, 0, 0))
    for item in items:
        place(canvas, item)
    target = ASSETS / filename
    canvas.save(target, optimize=True)
    print(f"{target.name}: {target.stat().st_size} bytes")


if __name__ == "__main__":
    build(STATIC, "retro_static.png")
    build(SIGNAL, "retro_signal.png")
