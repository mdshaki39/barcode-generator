"""
export_engine.py
Handles export to PNG, transparent PNG, and SVG formats.
"""
import numpy as np
import cv2
from io import BytesIO
import base64
import svgwrite
from PIL import Image


def to_png_bytes(bgr: np.ndarray, dpi: int = 300) -> bytes:
    """Convert BGR numpy array to PNG bytes."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    buf = BytesIO()
    img.save(buf, format='PNG', dpi=(dpi, dpi))
    return buf.getvalue()


def to_transparent_png_bytes(bgra: np.ndarray, dpi: int = 300) -> bytes:
    """Convert BGRA numpy array to transparent PNG bytes."""
    rgba = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)
    img = Image.fromarray(rgba, 'RGBA')
    buf = BytesIO()
    img.save(buf, format='PNG', dpi=(dpi, dpi))
    return buf.getvalue()


def to_base64_png(bgr: np.ndarray) -> str:
    """Return base64-encoded PNG string."""
    return base64.b64encode(to_png_bytes(bgr)).decode()


def to_base64_transparent_png(bgra: np.ndarray) -> str:
    """Return base64-encoded transparent PNG string."""
    return base64.b64encode(to_transparent_png_bytes(bgra)).decode()


def to_svg(bgr: np.ndarray, width: int = 600, height: int = 220) -> str:
    """
    Convert signature image to SVG by embedding it as a base64 PNG.
    This preserves all visual quality while providing an SVG container
    with proper viewBox for scaling.
    """
    png_b64 = base64.b64encode(to_png_bytes(bgr)).decode()
    dwg = svgwrite.Drawing(size=(f"{width}px", f"{height}px"),
                           viewBox=f"0 0 {width} {height}")
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))
    dwg.add(dwg.image(
        href=f"data:image/png;base64,{png_b64}",
        insert=(0, 0), size=(f"{width}px", f"{height}px")
    ))
    return dwg.tostring()


def to_svg_bytes(bgr: np.ndarray) -> bytes:
    return to_svg(bgr).encode('utf-8')


def to_base64_svg(bgr: np.ndarray) -> str:
    return base64.b64encode(to_svg_bytes(bgr)).decode()