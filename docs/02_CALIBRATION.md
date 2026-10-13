# Pre-Run Calibration

**Do not launch the full 1000-book batch until you have completed this.**

## Why calibrate

A systematic bug — wrong DPI mapping, Y-inversion, wrong reading order —
will replicate across every book. Calibration catches it on page 1
instead of page 200,000.

## 1. Pick a stratified sample

Choose 20–30 books that span your library's range:

| Stratum | What to include |
|:---|:---|
| modern_digital | Recent, clean PDFs |
| 1990s_scan | Older scans, moderate noise |
| historical_degraded | Faded, foxed, or low-contrast scans |
| multicolumn | Newspapers, journals |
| mixed_script | Arabic with embedded Latin/numbers |
| tabular | Financial or administrative forms |

Copy them into `input_books/` if not already there.

## 2. Run calibration on one book

```bash
python calibrate.py --sample input_books/book_modern_001.pdf --pages 1-5
```

This produces two files in `output_searchable/`:
- `book_modern_001.CALIBRATION.pdf` — the searchable PDF
- `book_modern_001.CALIBRATION.debug.pdf` — the visual overlay

## 3. Inspect the debug overlay

Open `book_modern_001.CALIBRATION.debug.pdf`. For every page, verify:

### ✅ Bbox alignment
- Colored rectangles sit **on actual text**, not in margins
- No rectangles extend off-page
- Small regions (headers, footnotes) are not wildly oversized

### ✅ Reading order (Arabic)
- The magenta order line runs **top-to-bottom, right-to-left**
- It does NOT jump back and forth across the page
- Multi-column pages are read column-by-column, right column first

### ✅ Text panel
- Every region has extracted text
- Text is Arabic (not boxes/tofu)
- No repeated phrases (hallucination)

### ❌ Common failures

| Symptom | Cause | Fix |
|:---|:---|:---|
| Boxes mirrored vertically | Y-inversion bug | Check `map_bbox_to_points` |
| Boxes offset by a constant | DPI mismatch | Use `w_pt / img.width` scaling |
| Order line zigzags | Reading-order sort wrong | Check `generate_with_layout` output order |
| Text panel empty | Font failed silently | Verify Amiri path |
| Repeated phrases | Runaway loop | Lower `MAX_NEW_TOKENS`, raise DPI |

## 4. Verify searchability

Open the calibration PDF in **Adobe Acrobat** (not just Preview/Chrome —
they disagree on Arabic search). Search for a word you can see on the page.

If search fails, run:

```python
from core.qa_validator import validate_arabic_text_layer
from pathlib import Path
print(validate_arabic_text_layer(Path("output_searchable/book_modern_001.CALIBRATION.pdf")))
```

A `FAIL` result means presentation-form characters are in the text layer.
This is a **font problem**, not a model problem. Re-check the Amiri path.

## 5. Calibrate across all strata

Repeat steps 2–4 for one book in each stratum. Record:

- DPI that worked best per stratum
- Any stratum where OCR quality is unacceptable
- Any stratum where a different threshold helps

If a stratum consistently fails, update `config.py`:

```python
DEFAULT_DPI = 400   # for historical_degraded
```

## 6. Sign-off checklist

Before launching the full run:

- [ ] Debug overlay verified for ≥1 book per stratum
- [ ] Arabic search works in Acrobat for every stratum
- [ ] `validate_arabic_text_layer` returns PASS for every stratum
- [ ] No runaway repetition on any calibration page
- [ ] `config.py` thresholds tuned if needed