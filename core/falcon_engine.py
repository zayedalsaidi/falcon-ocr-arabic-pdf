"""
In-process Falcon-OCR engine wrapper.

Uses generate_with_layout() so bboxes are returned in the pixel space of
the exact PIL image passed in — no HTTP round-trip, no coordinate ambiguity.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from PIL import Image
from typing import List, Dict, Any

from config import (
    MODEL_ID, DEVICE, DTYPE, MAX_NEW_TOKENS, TEMPERATURE,
    LAYOUT_THRESHOLD, CONTAINMENT_THRESHOLD,
)


class FalconOCREngine:
    """Singleton wrapper around the Falcon-OCR VLM."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        print(f"Loading Falcon-OCR model ({MODEL_ID})...")
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if DTYPE == "bfloat16" else torch.float16,
            device_map=DEVICE,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        self.model.eval()
        print("Model loaded.")

    @torch.inference_mode()
    def ocr_page(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Run layout + OCR on a single page image.
        Returns list of {category, bbox, score, text}.
        Bboxes are [x1, y1, x2, y2] in input-image pixel space.
        """
        results = self.model.generate_with_layout(
            image,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            layout_threshold=LAYOUT_THRESHOLD,
            containment_threshold=CONTAINMENT_THRESHOLD,
        )
        return results[0] if results else []

    @torch.inference_mode()
    def ocr_batch(self, images: List[Image.Image]) -> List[List[Dict[str, Any]]]:
        """Batch OCR for multiple page images."""
        return self.model.generate_with_layout(
            images,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            layout_threshold=LAYOUT_THRESHOLD,
            containment_threshold=CONTAINMENT_THRESHOLD,
        )