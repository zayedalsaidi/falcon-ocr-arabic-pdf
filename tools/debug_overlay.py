"""
Debug overlay generator.

Reads the per-page cache and renders a debug PDF with:
  - bbox rectangles (colored by category)
  - region index labels
  - reading-order line
  - extracted text side panel

Usage:
    python -m tools.debug_overlay --book <stem>
    python -m tools.debug_overlay --book <stem> --pages 5-20,42
    python -m tools.debug_overlay --book <stem> --layers bbox,order
    python -m tools.debug_overlay --compare <stemA> <stemB> --pages 10
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import fitz

from config import CACHE_DIR, OUTPUT_DIR, INPUT_DIR
from core.pdf_processor import map_bbox_to_points


CATEGORY_COLORS = {
    "text":            (0.00, 0.45, 0.80),
    "title":           (0.85, 0.10, 0.10),
    "section-header":  (0.90, 0.40, 0.00),
    "page-header":     (0.55, 0.55, 0.55),
    "page-footer":     (0.55, 0.55, 0.55),
    "footnote":        (0.60, 0.20, 0.70),
    "list-item":       (0.10, 0.60, 0.30),
    "table":           (0.70, 0.55, 0.00),
    "formula":         (0.00, 0.60, 0.60),
    "caption":         (0.80, 0.40, 0.60),
    "image":           (0.30, 0.30, 0.30),
    "plain":           (0.00, 0.45, 0.80),
}
DEFAULT_COLOR = (0.30, 0.30, 0.30)


def load_page_cache(book_stem: str, page_idx: int) -> Optional[Dict]:
    f = CACHE_DIR / book_stem / f"page_{page_idx:04d}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def parse_page_range(spec: str, total: int) -> List[int]:
    if not spec:
        return list(range(total))
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a) - 1, int(b)))
        else:
            out.add(int(part) - 1)
    return sorted(i for i in out if 0 <= i < total)


def _wrap(text: str, width: int) -> List[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_bbox(page, rect, color, width=1.0, label=None, size=7.0):
    page.draw_rect(rect, color=color, width=width, overlay=True)
    if label:
        page.insert_text(
            fitz.Point(rect.x0 + 1, max(rect.y0 - 1, size)),
            label, fontsize=size, color=color, render_mode=0,
        )


def draw_reading_order(page, rects, color=(0.9, 0.1, 0.9)):
    if len(rects) < 2:
        return
    centers = [fitz.Point(r.x0 + r.width / 2, r.y0 + r.height / 2) for r in rects]
    for i in range(len(centers) - 1):
        page.draw_line(centers[i], centers[i+1], color=color, width=0.6, overlay=True)
        page.insert_text(
            fitz.Point(centers[i].x + 2, centers[i].y),
            str(i + 1), fontsize=6, color=color, render_mode=0,
        )


def draw_text_panel(page, regions, page_rect, panel_width=200.0, font_size=6.0):
    panel = fitz.Rect(page_rect.x1, 0, page_rect.x1 + panel_width, page_rect.y1)
    page.draw_rect(panel, color=(0.9, 0.9, 0.9), fill=(0.98, 0.98, 0.95), overlay=True)

    y = 12.0
    page.insert_text(fitz.Point(panel.x0 + 4, y), "Extracted text",
                     fontsize=font_size + 1, color=(0, 0, 0))
    y += font_size + 4

    for i, region in enumerate(regions):
        text = region.get("text", "").strip()
        cat = region.get("category", "?")
        score = region.get("score", 0.0)
        page.insert_text(fitz.Point(panel.x0 + 4, y),
                         f"[{i}] {cat} ({score:.2f})",
                         fontsize=font_size, color=(0.2, 0.2, 0.6))
        y += font_size + 1
        for line in _wrap(text, 42):
            if y > panel.y1 - 6:
                page.insert_text(fitz.Point(panel.x0 + 4, y), "...",
                                 fontsize=font_size, color=(0.5, 0.5, 0.5))
                return
            page.insert_text(fitz.Point(panel.x0 + 6, y), line,
                             fontsize=font_size, color=(0.1, 0.1, 0.1))
            y += font_size + 1
        y += 3


def build_debug_pdf(book_stem, pages=None, layers=("bbox", "order", "text"),
                    output_name=None) -> Path:
    input_pdf = INPUT_DIR / f"{book_stem}.pdf"
    if not input_pdf.exists():
        raise FileNotFoundError(input_pdf)

    doc = fitz.open(input_pdf)
    total = len(doc)
    page_indices = pages if pages is not None else list(range(total))

    out = fitz.open()
    show_text = "text" in layers
    panel_width = 200.0 if show_text else 0.0

    for page_idx in page_indices:
        cached = load_page_cache(book_stem, page_idx)
        if cached is None:
            print(f"  [warn] no cache for page {page_idx + 1}")
            continue

        regions = cached["regions"]
        img_w, img_h = cached["img_width"], cached["img_height"]
        w_pt, h_pt = cached["page_width_pt"], cached["page_height_pt"]

        new_page = out.new_page(width=w_pt + panel_width, height=h_pt)
        pix = doc[page_idx].get_pixmap(dpi=cached["dpi"])
        new_page.insert_image(fitz.Rect(0, 0, w_pt, h_pt), pixmap=pix)

        rects = []
        for r in regions:
            b = r.get("bbox")
            rects.append(
                map_bbox_to_points(b, img_w, img_h, w_pt, h_pt)
                if b and len(b) == 4 else None
            )

        if "bbox" in layers:
            for i, (r, rect) in enumerate(zip(regions, rects)):
                if rect is None:
                    continue
                color = CATEGORY_COLORS.get(r.get("category", "").lower(), DEFAULT_COLOR)
                draw_bbox(new_page, rect, color, label=f"{i}:{r.get('category', '?')}")

        if "order" in layers:
            draw_reading_order(new_page, [r for r in rects if r is not None])

        if show_text:
            draw_text_panel(new_page, regions, fitz.Rect(0, 0, w_pt, h_pt), panel_width)

    if output_name is None:
        output_name = f"{book_stem}.debug.pdf"
    out_path = OUTPUT_DIR / output_name
    out.save(out_path)
    out.close(); doc.close()
    print(f"Debug PDF: {out_path}")
    return out_path


def build_comparison_pdf(book_a, book_b, pages=None, output_name=None) -> Path:
    doc_a = fitz.open(INPUT_DIR / f"{book_a}.pdf")
    doc_b = fitz.open(INPUT_DIR / f"{book_b}.pdf")
    total = min(len(doc_a), len(doc_b))
    page_indices = pages if pages is not None else list(range(total))

    out = fitz.open()
    for page_idx in page_indices:
        if page_idx >= total:
            continue
        ca = load_page_cache(book_a, page_idx)
        cb = load_page_cache(book_b, page_idx)
        if ca is None or cb is None:
            continue

        wa, ha = ca["page_width_pt"], ca["page_height_pt"]
        wb, hb = cb["page_width_pt"], cb["page_height_pt"]
        h = max(ha, hb)

        new_page = out.new_page(width=wa + wb, height=h)
        new_page.insert_image(fitz.Rect(0, 0, wa, ha),
                              pixmap=doc_a[page_idx].get_pixmap(dpi=ca["dpi"]))
        new_page.insert_image(fitz.Rect(wa, 0, wa + wb, hb),
                              pixmap=doc_b[page_idx].get_pixmap(dpi=cb["dpi"]))

        for cache, x_off in ((ca, 0.0), (cb, wa)):
            for i, r in enumerate(cache["regions"]):
                b = r.get("bbox")
                if not b or len(b) != 4:
                    continue
                rect = map_bbox_to_points(
                    b, cache["img_width"], cache["img_height"],
                    cache["page_width_pt"], cache["page_height_pt"],
                )
                rect = fitz.Rect(rect.x0 + x_off, rect.y0, rect.x1 + x_off, rect.y1)
                color = CATEGORY_COLORS.get(r.get("category", "").lower(), DEFAULT_COLOR)
                draw_bbox(new_page, rect, color, width=0.8, label=str(i))

        new_page.draw_line(fitz.Point(wa, 0), fitz.Point(wa, h),
                           color=(0.9, 0.1, 0.1), width=2.0)

    if output_name is None:
        output_name = f"{book_a}__vs__{book_b}.debug.pdf"
    out_path = OUTPUT_DIR / output_name
    out.save(out_path)
    out.close(); doc_a.close(); doc_b.close()
    print(f"Comparison PDF: {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Debug overlay generator")
    ap.add_argument("--book")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    ap.add_argument("--pages", default="")
    ap.add_argument("--layers", default="bbox,order,text")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    layers = tuple(l.strip() for l in args.layers.split(",") if l.strip())

    if args.compare:
        a, b = args.compare
        doc = fitz.open(INPUT_DIR / f"{a}.pdf")
        total = len(doc); doc.close()
        pages = parse_page_range(args.pages, total)
        build_comparison_pdf(a, b, pages=pages, output_name=args.out)
        return

    if not args.book:
        ap.error("Provide --book or --compare")

    doc = fitz.open(INPUT_DIR / f"{args.book}.pdf")
    total = len(doc); doc.close()
    pages = parse_page_range(args.pages, total)
    build_debug_pdf(args.book, pages=pages, layers=layers, output_name=args.out)


if __name__ == "__main__":
    main()