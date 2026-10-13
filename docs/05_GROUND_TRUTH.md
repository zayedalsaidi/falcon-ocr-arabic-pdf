# Ground-Truth CER (Optional)

**You do not need this to ship correct PDFs.** The automated gates in
`core/qa_validator.py` already catch the failures that matter for
searchability. Use this only when you want a numeric accuracy figure —
for tuning DPI, comparing configs, or reporting to a stakeholder.

## When to use it

- Choosing between 300 and 400 DPI for a stratum
- Comparing end-to-end vs layout mode objectively
- Tracking regressions across pipeline versions
- Reporting accuracy

## When to skip it

- You just want searchable PDFs
- The automated gates pass and visual spot-checks look good
- You don't have time to transcribe reference text

## Building the reference set

Transcribe 5–10 pages per stratum (not per book). Store them as:

```
ground_truth/
├── book_modern_001/
│   ├── page_0001.txt
│   ├── page_0007.txt
│   └── page_0012.txt
├── book_1990s_017/
│   └── page_0003.txt
└── ...
```

### Typing rules (critical)

1. **Logical order, not visual.** Read each word right-to-left and type
   letters in that order. This matches what PyMuPDF extracts from a
   correctly-built text layer.
2. **Base letters only.** No presentation forms (`ب` not `ﺒ`).
3. **Diacritics optional.** The normalizer strips them for scoring.
4. **Punctuation as-is.** Arabic commas and Latin commas both work.
5. **Illegible words:** write `[?]` and skip that page.

## Running the harness

After the pipeline finishes for a book, extract hypotheses and evaluate:

```python
import fitz
from tools.ground_truth import evaluate_book, save_ground_truth_report

stem = "book_modern_001"
doc = fitz.open(f"output_searchable/{stem}.pdf")
hypotheses = [page.get_text() for page in doc]
doc.close()

report = evaluate_book(stem, hypotheses, stratum="modern_digital")
save_ground_truth_report(stem, report)
```

Or wire it into `run_batch.py` after `build_searchable_pdf` — it's a
no-op if no reference files exist.

## Reading the numbers

| Metric | Meaning | Target |
|:---|:---|:---|
| `aggregate_strict_cer` | True accuracy after Arabic cleanup | < `MAX_CER_ARABIC` (0.15) |
| `aggregate_raw_cer` | Raw accuracy, diacritics included | Informational |
| `cosmetic_gap` | raw − strict | Large gap = cosmetic errors only |
| `mean_strict_wer` | Word-level accuracy | Closer to user perception |

## Length-weighted aggregation

CER is aggregated by character count, not per-page average. This is
standard practice — a 20-character header with one error should not
count as much as a 2000-character body with one error.

## Stratified reporting

Tag each book with a stratum when you evaluate:

```python
report = evaluate_book(stem, hypotheses, stratum="historical_degraded")
```

Then aggregate across the library:

```python
import json
from pathlib import Path
from tools.ground_truth import evaluate_library

reports = [json.loads(p.read_text()) for p in Path("qa_reports").glob("*.cer.json")]
print(json.dumps(evaluate_library(reports), indent=2, ensure_ascii=False))
```

You get per-stratum CER, which tells you whether the model holds up
across your library's range.