"""
Automated QA: structural checks + the Arabic presentation-form gate.

The presentation-form check is the single most important automated check
for Arabic searchable PDFs. Presence of U+FB50..U+FDFF or U+FE70..U+FEFF
means the text layer is corrupted and search will fail.
"""

import re
import json
import fitz
from pathlib import Path
from typing import Dict, Any, List, Tuple

from config import (
    MAX_CER_ARABIC, MIN_TEXT_COVERAGE_RATIO, MAX_REPETITION_RATIO,
    QA_REPORT_DIR,
)

PRESENTATION_FORMS = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")


def validate_arabic_text_layer(pdf_path: Path) -> Tuple[bool, str]:
    """Check every page for presentation-form characters."""
    doc = fitz.open(pdf_path)
    try:
        for page_num, page in enumerate(doc):
            matches = PRESENTATION_FORMS.findall(page.get_text())
            if matches:
                return False, (
                    f"Page {page_num + 1}: {len(matches)} presentation-form "
                    f"characters. Search will fail."
                )
    finally:
        doc.close()
    return True, "All pages clean."


def validate_page_structure(
    page_idx: int,
    regions: List[Dict[str, Any]],
    img_width: int,
    img_height: int,
    extracted_text: str,
) -> Tuple[bool, List[str]]:
    """Structural validation for a single page."""
    warnings = []

    # Bbox containment
    for region in regions:
        bbox = region.get("bbox")
        if not bbox or len(bbox) != 4:
            warnings.append(f"Page {page_idx+1}: region missing bbox")
            continue
        x1, y1, x2, y2 = bbox
        if not (0 <= x1 < x2 <= img_width and 0 <= y1 < y2 <= img_height):
            warnings.append(
                f"Page {page_idx+1}: bbox {bbox} out of bounds "
                f"({img_width}x{img_height})"
            )

    # Text density
    area = img_width * img_height
    if area > 0 and extracted_text.strip():
        ratio = len(extracted_text) / area
        if ratio < MIN_TEXT_COVERAGE_RATIO:
            warnings.append(f"Page {page_idx+1}: low text density ({ratio:.6f})")

    # Runaway repetition
    if extracted_text:
        words = extracted_text.split()
        if len(words) > 20:
            ngrams = {}
            for i in range(len(words) - 4):
                ng = " ".join(words[i:i+5])
                ngrams[ng] = ngrams.get(ng, 0) + 1
            if ngrams:
                ratio = max(ngrams.values()) / len(ngrams)
                if ratio > MAX_REPETITION_RATIO:
                    warnings.append(
                        f"Page {page_idx+1}: possible runaway repetition "
                        f"(ratio {ratio:.2f})"
                    )

    return len(warnings) == 0, warnings


def generate_qa_report(book_stem: str, page_results: List[Dict]) -> Dict:
    """Aggregate QA metrics for a completed book."""
    total = len(page_results)
    pages_with_warnings = sum(1 for p in page_results if p.get("warnings"))
    total_warnings = sum(len(p.get("warnings", [])) for p in page_results)

    return {
        "book": book_stem,
        "total_pages": total,
        "pages_with_warnings": pages_with_warnings,
        "total_warnings": total_warnings,
        "pass_rate": (total - pages_with_warnings) / total if total else 0,
    }


def save_qa_report(book_stem: str, report: Dict):
    out = QA_REPORT_DIR / f"{book_stem}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)