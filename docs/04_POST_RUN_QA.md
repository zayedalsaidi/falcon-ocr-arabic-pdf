# Post-Run QA

After the full batch finishes, run these checks in order.

## 1. Coverage check

How many books completed?

```bash
ls input_books/*.pdf | wc -l
ls output_searchable/*.pdf | wc -l
ls output_searchable/*.BAD.pdf 2>/dev/null | wc -l
```

Every input should have an output. `.BAD.pdf` files are books that
failed the Arabic gate and need investigation.

## 2. Automated QA summary

Aggregate all QA reports:

```bash
python - <<'PY'
import json
from pathlib import Path

reports = [json.loads(p.read_text()) for p in Path("qa_reports").glob("*.json")]
total_books = len(reports)
total_pages = sum(r["total_pages"] for r in reports)
total_warnings = sum(r["total_warnings"] for r in reports)
clean_books = sum(1 for r in reports if r["pages_with_warnings"] == 0)

print(f"Books: {total_books}")
print(f"Pages: {total_pages}")
print(f"Clean books: {clean_books} / {total_books}")
print(f"Total warnings: {total_warnings}")

# Worst books
worst = sorted(reports, key=lambda r: r["pass_rate"])[:10]
for r in worst:
    print(f"  {r['book']}: {r['pass_rate']:.1%} pass")
PY
```

## 3. Critical Arabic gate

Every output PDF must pass:

```bash
python - <<'PY'
from pathlib import Path
from core.qa_validator import validate_arabic_text_layer

failures = []
for pdf in Path("output_searchable").glob("*.pdf"):
    if pdf.name.endswith(".debug.pdf"):
        continue
    ok, msg = validate_arabic_text_layer(pdf)
    if not ok:
        failures.append((pdf.name, msg))

print(f"Checked. Failures: {len(failures)}")
for name, msg in failures:
    print(f"  {name}: {msg}")
PY
```

A non-zero failure count means those books are not searchable. Move them
to a quarantine folder and re-process.

## 4. Spot-check visually

For each stratum, pick 2–3 books and generate a debug overlay:

```bash
python -m tools.debug_overlay --book <stem> --pages 1-10
```

Open the debug PDF and verify:
- Bboxes still align
- Reading order still correct
- Text panel populated

This catches regressions that the automated gates miss (e.g., systematic
misalignment that stays within bounds).

## 5. Sample the output PDFs

Open a handful of finished PDFs in Adobe Acrobat:

- Search for a word you can see on the page → should highlight correctly
- Copy a paragraph → should paste as readable Arabic (logical order)
- Select-all → should include all pages, not just one

If copy-paste produces reversed or disconnected Arabic, the text layer
uses presentation forms — re-check Amiri and re-process.

## 6. Optional: CER on a sample

If you built ground truth for a stratum, run:

```python
import json
from pathlib import Path
from tools.ground_truth import evaluate_library

reports = [json.loads(p.read_text()) for p in Path("qa_reports").glob("*.cer.json")]
summary = evaluate_library(reports)
print(json.dumps(summary, indent=2, ensure_ascii=False))
```

Compare `aggregate_strict_cer` against `MAX_CER_ARABIC` in `config.py`.

## 7. Sign-off checklist

- [ ] All input books have a corresponding output
- [ ] No `.BAD.pdf` files remain uninvestigated
- [ ] `validate_arabic_text_layer` passes on every output
- [ ] Debug overlay spot-checks pass for every stratum
- [ ] Adobe Acrobat search works on sampled books
- [ ] QA report pass rate is acceptable (target ≥95%)
- [ ] (Optional) CER is within `MAX_CER_ARABIC`