"""
PDF page rendering and coordinate mapping.

CRITICAL: Both PyMuPDF and Falcon-OCR use top-left origin.
Do NOT invert the Y-axis when mapping bboxes to points.
"""

import fitz  # PyMuPDF
from PIL import Image
from typing import List, Tuple

from config import DEFAULT_DPI, MIN_DPI, MAX_DPI


def get_page_dpi(page: fitz.Page) -> float:
    """Estimate native DPI of the embedded scan, clamped to safe range."""
    image_list = page.get_images(full=True)
    if not image_list:
        return DEFAULT_DPI

    xref = image_list[0][0]
    base_image = page.doc.extract_image(xref)
    img_width_px = base_image["width"]
    page_width_pt = page.rect.width

    if page_width_pt > 0:
        calculated = (img_width_px / page_width_pt) * 72
        return max(MIN_DPI, min(MAX_DPI, round(calculated, -1)))
    return DEFAULT_DPI


def render_page_to_pil(page: fitz.Page, dpi: float = None) -> Tuple[Image.Image, float]:
    """Render a PDF page to a PIL image. Returns (image, effective_dpi)."""
    if dpi is None:
        dpi = get_page_dpi(page)
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img, dpi


def map_bbox_to_points(
    bbox_pixels: List[float],
    img_width_px: int,
    img_height_px: int,
    page_width_pt: float,
    page_height_pt: float,
) -> fitz.Rect:
    """
    Map bbox from image pixel space to PDF points.
    Top-left origin on both sides -> no Y inversion.
    """
    sx = page_width_pt / img_width_px
    sy = page_height_pt / img_height_px
    x1, y1, x2, y2 = bbox_pixels
    return fitz.Rect(x1 * sx, y1 * sy, x2 * sx, y2 * sy)