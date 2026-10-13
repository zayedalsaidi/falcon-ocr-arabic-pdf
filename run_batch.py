"""
Main orchestrator. Processes all PDFs in input_books/, one at a time,
with per-page caching for resume-ability and automated QA per book.
"""

import json
import fitz
from pathlib import Path
from tqdm import tqdm

from config import INPUT_DIR, OUTPUT_DIR, CACHE_DIR, LOG_DIR, QA_REPORT_DIR
from core.falcon_engine import FalconOCREngine
from core.pdf_processor import render_page_to_pil
from core.pdf_builder import build_searchable_pdf, detect_font
from core.qa_validator import (
    validate_page_structure,
    validate_arabic_text_layer,
    generate_qa_report,
    save_qa_report,
)


def page_cache_path(book_stem: str, page_idx: int) -> Path:
    d = CACHE_DIR / book_stem
    d.mkdir(parents=True, exist_ok=True)
    return d / f"page_{page_idx:04d}.json"


def process_book(pdf_path: Path, engine: FalconOCREngine):
    stem = pdf_path.stem
    output_pdf = OUTPUT_DIR / f"{stem}.pdf"
    qa_report_path = QA_REPORT_DIR / f"{stem}.json"

    if output_pdf.exists() and qa_report_path.exists():
        print(f"Skipping already processed: {stem}")
        return

    print(f"\n--- Processing: {pdf_path.name} ---")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    font_path, font_name = detect_font(pdf_path.name)

    page_images, page_regions, page_metrics, all_qa = [], [], [], []

    for page_idx in tqdm(range(total_pages), desc=f"  {stem}"):
        page = doc[page_idx]
        cache_file = page_cache_path(stem, page_idx)

        if cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            regions = cached["regions"]
            img, _ = render_page_to_pil(page, dpi=cached["dpi"])
        else:
            img, img_dpi = render_page_to_pil(page)
            regions = engine.ocr_page(img)
            cache_file.write_text(
                json.dumps({
                    "regions": regions,
                    "dpi": img_dpi,
                    "img_width": img.width,
                    "img_height": img.height,
                    "page_width_pt": page.rect.width,
                    "page_height_pt": page.rect.height,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        extracted = "\n".join(r.get("text", "") for r in regions)
        _, warnings = validate_page_structure(
            page_idx, regions, img.width, img.height, extracted
        )
        for w in warnings:
            print(f"  [QA] {w}")

        page_images.append(img)
        page_regions.append(regions)
        page_metrics.append({
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
        })
        all_qa.append({"page_idx": page_idx, "warnings": warnings})

    doc.close()

    build_searchable_pdf(
        output_pdf_path=output_pdf,
        page_images=page_images,
        page_regions=page_regions,
        page_metrics=page_metrics,
        font_path=font_path,
        font_name=font_name,
    )

    # CRITICAL Arabic gate — inspect the OUTPUT PDF, not the OCR output
    ok, msg = validate_arabic_text_layer(output_pdf)
    if not ok:
        print(f"  [CRITICAL QA FAIL] {msg}")
        bad_path = output_pdf.with_suffix(".BAD.pdf")
        output_pdf.rename(bad_path)
        print(f"  Moved to {bad_path}")
        return

    report = generate_qa_report(stem, all_qa)
    report["arabic_check"] = msg
    report["pdf_built"] = str(output_pdf)
    save_qa_report(stem, report)
    print(f"  Completed: {output_pdf.name} | pass rate: {report['pass_rate']:.1%}")


def main():
    engine = FalconOCREngine()
    books = sorted(INPUT_DIR.glob("*.pdf"))
    print(f"Found {len(books)} books in {INPUT_DIR}")

    for book in books:
        try:
            process_book(book, engine)
        except Exception as e:
            print(f"  [ERROR] {book.name}: {e}")
            with open(LOG_DIR / "errors.log", "a", encoding="utf-8") as f:
                f.write(f"{book.name}: {e}\n")


if __name__ == "__main__":
    main()