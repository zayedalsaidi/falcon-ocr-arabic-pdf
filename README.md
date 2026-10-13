# Falcon-OCR Arabic Searchable PDF Pipeline

Convert scanned Arabic PDF books into searchable PDFs using [TII's Falcon-OCR](https://huggingface.co/tiiuae/Falcon-OCR) model, run in-process via `generate_with_layout`.

**Correctness-first design** for large heterogeneous libraries (1000+ books, mixed DPI, mixed eras).

---

## 🚀 Quick Start

Follow these steps in order. Do not skip step 4 — calibration is what protects you from replicating a bug across 1000 books.

### Step 1 — Install dependencies

```bash
# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install PyTorch with CUDA 12.8 (Blackwell / sm_120 support)
pip install torch --index-url https://download.pytorch.org/whl/cu128

# Install the rest
pip install -r requirements.txt
```

Verify PyTorch sees your GPU:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
# Expected: True 12.8
```

### Step 2 — Install Arabic fonts (CRITICAL)

Only **Amiri** produces searchable Arabic base letters. Using any other font will produce a PDF that looks correct but fails search.

```bash
sudo apt install fonts-hosny-amiri fonts-dejavu

# Verify paths
ls /usr/share/fonts/truetype/amiri/Amiri-Regular.ttf
ls /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
```

If your distro places fonts elsewhere, update `ARABIC_FONT_PATH` and `ENGLISH_FONT_PATH` in `config.py`.

### Step 3 — Sanity-check the model loads

```bash
python -c "from core.falcon_engine import FalconOCREngine; FalconOCREngine()"
```

Expected: `Model loaded.` — the first call downloads weights and builds FlexAttention kernels (2–5 minutes).

### Step 4 — Calibrate on a sample book

**Do this before processing the full library.**

```bash
# Copy a sample book into input_books/ (or place your own)
cp /path/to/sample.pdf input_books/book_modern_001.pdf

# Run calibration on the first 5 pages
python calibrate.py --sample input_books/book_modern_001.pdf --pages 1-5
```

This produces two files in `output_searchable/`:

| File | What it is |
|:---|:---|
| `book_modern_001.CALIBRATION.pdf` | The searchable PDF |
| `book_modern_001.CALIBRATION.debug.pdf` | Visual overlay for inspection |

### Step 5 — Inspect the debug overlay

Open `output_searchable/book_modern_001.CALIBRATION.debug.pdf`. For every page, verify:

- ✅ **Bbox alignment** — colored rectangles sit on actual text, not in margins
- ✅ **Reading order** — magenta line runs top-to-bottom, right-to-left
- ✅ **Text panel** — every region has extracted Arabic text, no repeats

See `docs/02_CALIBRATION.md` for the full checklist and common failure symptoms.

### Step 6 — Verify searchability in Acrobat

Open the calibration PDF in **Adobe Acrobat** (not Preview or Chrome — they disagree on Arabic search). Search for a word you can see on the page.

If search fails, run the automated gate:

```bash
python - <<'PY'
from pathlib import Path
from core.qa_validator import validate_arabic_text_layer
print(validate_arabic_text_layer(Path("output_searchable/book_modern_001.CALIBRATION.pdf")))
PY
```

`FAIL` means a font problem. Re-check the Amiri path in `config.py`.

### Step 7 — Calibrate across all strata

Repeat steps 4–6 for **one book per stratum** in your library:

| Stratum | Example |
|:---|:---|
| `modern_digital` | Recent clean PDFs |
| `1990s_scan` | Older scans, moderate noise |
| `historical_degraded` | Faded, low-contrast scans |
| `multicolumn` | Newspapers, journals |
| `mixed_script` | Arabic with embedded Latin/numbers |
| `tabular` | Financial forms, tables |

If a stratum consistently fails, tune `config.py`:

```python
DEFAULT_DPI = 400   # for historical_degraded
```

### Step 8 — Run a pilot batch (~50 books)

Copy ~50 books into `input_books/` and run:

```bash
python run_batch.py
```

Check the QA reports:

```bash
ls qa_reports/ | wc -l
cat qa_reports/book_modern_001.json
```

Target: ≥95% pages without warnings per book. Investigate any book below that before the full run.

### Step 9 — Launch the full batch

```bash
python run_batch.py
```

**Properties of this run:**

- **Resumable** — per-page JSON cache in `page_cache/`. A crash costs one page, not one book.
- **Idempotent** — already-processed books are skipped automatically.
- **Safe** — books failing the Arabic gate are renamed to `*.BAD.pdf` and skipped.

To re-process a single book, delete its outputs first:

```bash
rm qa_reports/<stem>.json output_searchable/<stem>.pdf
python run_batch.py
```

### Step 10 — Post-run QA

Run the full QA suite from `docs/04_POST_RUN_QA.md`. The short version:

```bash
# Coverage
ls input_books/*.pdf | wc -l
ls output_searchable/*.pdf | grep -v debug | wc -l
ls output_searchable/*.BAD.pdf 2>/dev/null | wc -l

# Critical Arabic gate across every output
python - <<'PY'
from pathlib import Path
from core.qa_validator import validate_arabic_text_layer

failures = []
for pdf in Path("output_searchable").glob("*.pdf"):
    if pdf.name.endswith(".debug.pdf"): continue
    ok, msg = validate_arabic_text_layer(pdf)
    if not ok:
        failures.append((pdf.name, msg))

print(f"Failures: {len(failures)}")
for name, msg in failures:
    print(f"  {name}: {msg}")
PY
```

Then spot-check visually per stratum:

```bash
python -m tools.debug_overlay --book <stem> --pages 1-10
```

---

## 🛠 Debugging

When the QA report flags a page, or a book looks correct but isn't searchable:

```bash
# Visual overlay (reads cache, no OCR re-run)
python -m tools.debug_overlay --book book_modern_001
python -m tools.debug_overlay --book book_modern_001 --pages 5-20,42
python -m tools.debug_overlay --book book_modern_001 --layers bbox,order

# Compare two runs side-by-side
python -m tools.debug_overlay --compare book_v1 book_v2 --pages 10-15
```

Full debugging guide: `docs/03_DEBUGGING.md`.

---

## 📁 Project Layout

```
ocr_project/
├── README.md                       ← you are here
├── requirements.txt
├── config.py                       ← edit paths and thresholds here
│
├── core/                           Production pipeline
│   ├── falcon_engine.py            In-process model wrapper
│   ├── pdf_processor.py            Rendering + coordinate mapping
│   ├── pdf_builder.py              Searchable PDF assembly
│   └── qa_validator.py             Structural + Arabic text-layer QA
│
├── tools/                          Optional / manual use
│   ├── debug_overlay.py            Visual inspector
│   └── ground_truth.py             Optional CER harness
│
├── run_batch.py                    Main orchestrator
├── calibrate.py                    Pre-run calibration
│
├── docs/
│   ├── 01_INSTALL.md               Full install guide
│   ├── 02_CALIBRATION.md           Pre-run QA checklist
│   ├── 03_DEBUGGING.md             How to inspect and fix
│   ├── 04_POST_RUN_QA.md           Post-run verification
│   └── 05_GROUND_TRUTH.md          Optional CER setup
│
├── input_books/                    Source PDFs (gitignored)
├── output_searchable/              Searchable PDFs (gitignored)
├── page_cache/                     Per-page JSON (gitignored)
├── qa_reports/                     Per-book QA (gitignored)
├── logs/                           Error logs (gitignored)
└── ground_truth/                   Optional reference text (gitignored)
```

---

## 🔑 Three Rules to Remember

1. **Amiri for Arabic.** Only Amiri produces searchable base letters. If the font path is wrong, the pipeline raises `RuntimeError` — no silent fallback.
2. **No Y-inversion.** Both PyMuPDF and Falcon use top-left origin. Bbox → point mapping is `x * (w_pt / img_w)`, `y * (h_pt / img_h)`.
3. **Calibrate first.** Never launch the full batch before the debug overlay looks correct on every stratum.

---

## 📊 Timing Expectations

| Stage | Duration (1000 books, ~200k pages) |
|:---|:---|
| Install + first model load | 10–20 minutes |
| Calibration (one book per stratum) | 1–2 hours |
| Pilot batch (50 books) | 4–8 hours |
| Full batch | 3–7 days wall-clock |
| Post-run QA | 2–4 hours |

Throughput depends on GPU and stratum DPI. Plan for higher DPI on `historical_degraded` books.

---

## 📚 Full Documentation

| Topic | File |
|:---|:---|
| Installation details | `docs/01_INSTALL.md` |
| Pre-run calibration | `docs/02_CALIBRATION.md` |
| Debugging failures | `docs/03_DEBUGGING.md` |
| Post-run QA | `docs/04_POST_RUN_QA.md` |
| Ground-truth CER (optional) | `docs/05_GROUND_TRUTH.md` |

---

## ⚖️ License & Attribution

- Model: [tiiuae/Falcon-OCR](https://huggingface.co/tiiuae/Falcon-OCR)
- Inference engine: [tiiuae/Falcon-Perception](https://github.com/tiiuae/Falcon-Perception)
- Fonts: Amiri (SIL OFL), DejaVu (Bitstream Vera)
- Pipeline: this repository
