# Debugging

## When to debug

You'll reach for these tools when:
- The QA report flags pages in a book
- A book looks correct but isn't searchable
- Output quality regressed after a change
- You want to verify a specific page before shipping

## 1. The debug overlay (primary tool)

Rebuild the visual overlay from the existing cache — **no OCR re-run**:

```bash
# Whole book
python -m tools.debug_overlay --book book_modern_001

# Specific pages (1-based)
python -m tools.debug_overlay --book book_modern_001 --pages 5-20,42,100

# Only bboxes (no side panel, wider view)
python -m tools.debug_overlay --book book_modern_001 --layers bbox

# Only reading order
python -m tools.debug_overlay --book book_modern_001 --layers bbox,order

# Custom output name
python -m tools.debug_overlay --book book_modern_001 --out my_inspection.pdf
```

Output is written to `output_searchable/<book>.debug.pdf`.

## 2. Reading the overlay

| Layer | Color | What it means |
|:---|:---|:---|
| `text` | Blue | Body text |
| `title` | Red | Title / heading |
| `section-header` | Orange | Section break |
| `table` | Gold | Table region |
| `footnote` | Purple | Footnote |
| `page-header/footer` | Gray | Running header/footer |
| Reading order | Magenta | Processing order |

## 3. Comparing two runs

After changing DPI or model config, compare old vs new:

```bash
python -m tools.debug_overlay --compare book_v1 book_v2 --pages 10-15
```

Left = first book, right = second. Red divider in the middle.

## 4. Inspecting the raw cache

Every page's OCR output is in `page_cache/<stem>/page_NNNN.json`:

```bash
cat page_cache/book_modern_001/page_0005.json | python -m json.tool | head -50
```

Each region has `category`, `bbox`, `score`, `text`. This is the ground
truth for everything the debug overlay shows.

## 5. Common problems and fixes

### Text is present in cache but not in PDF
Font issue. Verify `ARABIC_FONT_PATH` exists and is readable. The
pipeline raises a `RuntimeError` on font failure — check `logs/errors.log`.

### PDF opens but text is not searchable
Run the presentation-form check:

```python
from core.qa_validator import validate_arabic_text_layer
from pathlib import Path
print(validate_arabic_text_layer(Path("output_searchable/<stem>.pdf")))
```

If FAIL, the font is writing presentation forms. Only Amiri avoids this.

### Bboxes misaligned
1. Open the debug overlay
2. If boxes are shifted by a constant → DPI mismatch
3. If boxes are mirrored → Y-inversion
4. If boxes are scaled wrong → aspect-ratio mismatch

Re-run calibration on a single page after fixing `core/pdf_processor.py`.

### Pages missing from output
Check `logs/errors.log`. If a page crashed during OCR, its cache will
be missing. Re-run — the pipeline will fill in the gap.

### Runaway repetition
The QA report flags these. Fix by:
- Raising DPI for that book
- Lowering `MAX_NEW_TOKENS` in `config.py`
- Falling back to layout mode (already default)

## 6. Re-OCR a single page

Delete the page's cache and re-run:

```bash
rm page_cache/<stem>/page_0012.json
python run_batch.py   # will re-process only the missing page
```

The book-level skip is bypassed by deleting `qa_reports/<stem>.json` too:

```bash
rm qa_reports/<stem>.json output_searchable/<stem>.pdf
python run_batch.py
```