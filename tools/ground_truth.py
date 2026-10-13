"""
OPTIONAL ground-truth CER harness.

Only needed if you want a numeric accuracy measurement. Requires
hand-transcribed reference text in logical Unicode order:
    ground_truth/<book_stem>/page_0001.txt
    ground_truth/<book_stem>/page_0002.txt
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

from config import GROUND_TRUTH_DIR, QA_REPORT_DIR

ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC"
    r"\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED\u0640]"
)
ALEF_VARIANTS = re.compile(r"[\u0622\u0623\u0625\u0671]")
YAA_VARIANTS = re.compile(r"[\u0649\u06CC]")
TAA_MARBUTA = re.compile(r"\u0629")
ARABIC_INDIC_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    "\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9",
    "01234567890123456789",
)
ARABIC_PUNCT = str.maketrans({
    "\u060C": ",", "\u061B": ";", "\u061F": "?", "\u066A": "%",
})
WHITESPACE = re.compile(r"\s+")


def normalize_arabic(text: str, level: str = "strict") -> str:
    if level == "raw":
        return text
    text = unicodedata.normalize("NFC", text)
    if level in ("light", "strict"):
        text = ARABIC_DIACRITICS.sub("", text)
        text = WHITESPACE.sub(" ", text).strip()
    if level == "strict":
        text = ALEF_VARIANTS.sub("\u0627", text)
        text = YAA_VARIANTS.sub("\u064A", text)
        text = TAA_MARBUTA.sub("\u0647", text)
        text = text.translate(ARABIC_INDIC_DIGITS)
        text = text.translate(ARABIC_PUNCT)
    return text


def levenshtein(ref: str, hyp: str) -> int:
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, start=1):
        curr = [i] + [0] * len(hyp)
        for j, hc in enumerate(hyp, start=1):
            cost = 0 if rc == hc else 1
            curr[j] = min(prev[j] + 1, curr[j-1] + 1, prev[j-1] + cost)
        prev = curr
    return prev[-1]


def compute_cer(reference: str, hypothesis: str, level: str = "strict") -> float:
    ref = normalize_arabic(reference, level)
    hyp = normalize_arabic(hypothesis, level)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def compute_wer(reference: str, hypothesis: str, level: str = "strict") -> float:
    ref = normalize_arabic(reference, level).split()
    hyp = normalize_arabic(hypothesis, level).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def load_reference_page(book_stem: str, page_idx: int) -> Optional[str]:
    f = GROUND_TRUTH_DIR / book_stem / f"page_{page_idx + 1:04d}.txt"
    return f.read_text(encoding="utf-8") if f.exists() else None


def evaluate_page(page_idx: int, reference: str, hypothesis: str) -> Dict:
    return {
        "page_idx": page_idx,
        "ref_len": len(reference),
        "hyp_len": len(hypothesis),
        "raw_cer":    round(compute_cer(reference, hypothesis, "raw"), 4),
        "light_cer":  round(compute_cer(reference, hypothesis, "light"), 4),
        "strict_cer": round(compute_cer(reference, hypothesis, "strict"), 4),
        "strict_wer": round(compute_wer(reference, hypothesis, "strict"), 4),
    }


def evaluate_book(book_stem: str, hypotheses_per_page: List[str],
                  stratum: Optional[str] = None) -> Dict:
    results = []
    for i, hyp in enumerate(hypotheses_per_page):
        ref = load_reference_page(book_stem, i)
        if ref and ref.strip():
            results.append(evaluate_page(i, ref, hyp))

    if not results:
        return {"book": book_stem, "stratum": stratum,
                "pages_evaluated": 0, "note": "No reference files."}

    total_ref = sum(r["ref_len"] for r in results)
    weighted_strict = sum(r["strict_cer"] * r["ref_len"] for r in results) / total_ref
    weighted_raw    = sum(r["raw_cer"]    * r["ref_len"] for r in results) / total_ref
    mean_wer        = sum(r["strict_wer"] for r in results) / len(results)

    return {
        "book": book_stem,
        "stratum": stratum,
        "pages_evaluated": len(results),
        "total_ref_chars": total_ref,
        "aggregate_strict_cer": round(weighted_strict, 4),
        "aggregate_raw_cer":    round(weighted_raw, 4),
        "mean_strict_wer":      round(mean_wer, 4),
        "cosmetic_gap":         round(weighted_raw - weighted_strict, 4),
        "worst_pages": sorted(results, key=lambda p: p["strict_cer"],
                              reverse=True)[:5],
        "page_results": results,
    }


def save_ground_truth_report(book_stem: str, report: Dict):
    out = QA_REPORT_DIR / f"{book_stem}.cer.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  [CER] {book_stem}: strict CER = "
          f"{report.get('aggregate_strict_cer')} "
          f"({report.get('pages_evaluated')} pages)")