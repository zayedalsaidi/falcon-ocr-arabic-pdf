"""
Searchable PDF assembly: scan image + invisible text layer.
Uses Amiri for Arabic. Uses insert_text (not insert_textbox) to avoid
silent fitting failures.
"""

import re
import fitz
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image

from config import ARABIC_FONT_PATH, ENGLISH_FONT_PATH
from core.pdf_processor import map_bbox_to_points


def detect_font(book_filename: str) -> tuple:
    """Arabic filenames get Amiri; ASCII filenames get DejaVu Sans."""
    if re.match(r"^[\x00-\x7F]+$", book_filename):
        return ENGLISH_FONT_PATH, "EnglishFont"
    return ARABIC_FONT_PATH, "ArabicFont"


def build_searchable_pdf(
    output_pdf_path: Path,
    page_images: List[Image.Image],
    page_regions: List[List[Dict[str, Any]]],
    page_metrics: List[Dict],
    font_path: str,
    font_name: str,
) -> List[Dict]:
    """Assemble sandwich PDF. Returns per-page QA metadata."""
    doc = fitz.open()
    qa_results = []

    for page_idx, (img, regions, metrics) in enumerate(
        zip(page_images, page_regions, page_metrics)
    ):
        w_pt = metrics["width_pt"]
        h_pt = metrics["height_pt"]
        new_page = doc.new_page(width=w_pt, height=h_pt)

        # Layer 1: visible scan
        pix = fitz.Pixmap(
            fitz.csRGB,
            fitz.IRect(0, 0, img.width, img.height),
            img.tobytes(),
        )
        new_page.insert_image(new_page.rect, pixmap=pix)

        # Layer 2: invisible searchable text
        page_text = []
        for region in regions:
            text = region.get("text", "").strip()
            if not text:
                continue
            bbox = region.get("bbox")
            if not bbox or len(bbox) != 4:
                continue

            pdf_rect = map_bbox_to_points(bbox, img.width, img.height, w_pt, h_pt)

            try:
                new_page.insert_text(
                    fitz.Point(pdf_rect.x0, pdf_rect.y1),
                    text,
                    fontsize=10,
                    fontname=font_name,
                    fontfile=font_path,
                    render_mode=3,  # invisible
                )
            except Exception as e:
                # Fail loudly — no silent font fallback
                raise RuntimeError(
                    f"Font error on page {page_idx + 1}: {e}"
                ) from e

            page_text.append(text)

        qa_results.append({
            "page_idx": page_idx,
            "regions_count": len(regions),
            "text_length": len("".join(page_text)),
        })

    doc.save(output_pdf_path)
    doc.close()
    return qa_results