"""
Central configuration for the Falcon-OCR Arabic pipeline.

Edit paths and thresholds here. Everything else imports from this module.
"""

import os
from pathlib import Path

# ============================================================
# Directories
# ============================================================
BASE_DIR = Path(os.getenv("OCR_BASE_DIR", ".")).resolve()

INPUT_DIR       = BASE_DIR / "input_books"
OUTPUT_DIR      = BASE_DIR / "output_searchable"
CACHE_DIR       = BASE_DIR / "page_cache"
LOG_DIR         = BASE_DIR / "logs"
QA_REPORT_DIR   = BASE_DIR / "qa_reports"
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth"

for _d in (INPUT_DIR, OUTPUT_DIR, CACHE_DIR, LOG_DIR, QA_REPORT_DIR, GROUND_TRUTH_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ============================================================
# Model
# ============================================================
MODEL_ID = "tiiuae/Falcon-OCR"
DEVICE   = "cuda"
DTYPE    = "bfloat16"

# ============================================================
# Rendering
# ============================================================
DEFAULT_DPI = 300
MIN_DPI     = 200
MAX_DPI     = 400

# ============================================================
# OCR Generation
# ============================================================
MAX_NEW_TOKENS          = 4096
TEMPERATURE             = 0.0
LAYOUT_THRESHOLD        = 0.3
CONTAINMENT_THRESHOLD   = 0.8

# ============================================================
# QA Thresholds
# ============================================================
MAX_CER_ARABIC             = 0.15     # 15% ceiling for Arabic
MIN_TEXT_COVERAGE_RATIO    = 0.0005   # chars per pixel area
MAX_REPETITION_RATIO       = 0.30     # runaway loop detector

# ============================================================
# Fonts — CRITICAL for searchable Arabic
# Amiri is the only tested font that produces searchable Arabic base letters.
# ============================================================
ARABIC_FONT_PATH  = "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"
ENGLISH_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# ============================================================
# Batch
# ============================================================
BATCH_SIZE = 4   # Pages per forward pass