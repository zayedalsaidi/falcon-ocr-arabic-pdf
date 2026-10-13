"""
Pre-run calibration harness.

Renders a few pages of a book, runs OCR, and writes a debug PDF +
a summary report. Run this BEFORE the full batch to verify:
  - bbox alignment
  - Arabic reading order
  - text-layer searchability
"""

import argparse
import fitz
from pathlib import Path

from config import INPUT_DIR, OUTPUT_DIR, CACHE_DIR
from core.falcon_engine import FalconOCREngine
from core.pdf_processor import render_page_to_pil
from core.pdf_builder import build_searchable_pdf, detect_font
from core.qa_validator import validate_arabic_text_layer
from tools.debug_overlay import build_debug_pdf


def calibrate(pdf_path: Path, pages: list[int]):
    stem = pdf_path.stem
    print(f"\n=== Calibrating {stem} ===")

    engine = FalconOCREngine()
    doc = fitz.open(pdf_path)
    font_path, font_name = detect_font(pdf_path.name)

    page_images, page_regions, page_metrics = [], [], []

    for page_idx in pages:
        page = doc[page_idx]
        img, dpi = render_page_to_pil(page)
        regions = engine.ocr_page(img)

        # Persist to the same cache the production pipeline will use
        cache_dir = CACHE_DIR / stem
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"page_{page_idx:04d}.json").write_text(
            __import__("json").dumps({
                "regions": regions,
                "dpi": dpi,
                "img_width": img.width,
                "img_height": img.height,
                "page_width_pt": page.rect.width,
                "page_height_pt": page.rect.height,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        page_images.append(img)
        page_regions.append(regions)
        page_metrics.append({
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
        })
        print(f"  Page {page_idx+1}: {len(regions)} regions")

    doc.close()

    out_pdf = OUTPUT_DIR / f"{stem}.CALIBRATION.pdf"
    build_searchable_pdf(
        output_pdf_path=out_pdf,
        page_images=page_images,
        page_regions=page_regions,
        page_metrics=page_metrics,
        font_path=font_path,
        font_name=font_name,
    )

    ok, msg = validate_arabic_text_layer(out_pdf)
    print(f"  Arabic searchability: {'PASS' if ok else 'FAIL'} — {msg}")

    # Build a debug overlay on the same pages
    build_debug_pdf(
        book_stem=stem,
        pages=pages,
        layers=("bbox", "order", "text"),
        output_name=f"{stem}.CALIBRATION.debug.pdf",
    )

    print(f"\nOpen these to verify:")
    print(f"  {out_pdf}")
    print(f"  {OUTPUT_DIR / f'{stem}.CALIBRATION.debug.pdf'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True, help="Path to a sample PDF")
    ap.add_argument("--pages", default="1-5",
                    help="Page range, e.g. 1-5 or 3,7,10 (1-based)")
    args = ap.parse_args()

    pdf = Path(args.sample)
    if not pdf.is_absolute():
        pdf = INPUT_DIR / pdf

    doc = fitz.open(pdf)
    total = len(doc); doc.close()

    selected = []
    for part in args.pages.split(","):
        if "-" in part:
            a, b = part.split("-")
            selected.extend(range(int(a) - 1, int(b)))
        else:
            selected.append(int(part) - 1)
    selected = [p for p in selected if 0 <= p < total]

    calibrate(pdf, selected)