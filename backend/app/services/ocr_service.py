import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


@dataclass
class OcrResult:
    text: str
    confidence: float | None
    raw_result_json: str
    error_code: str | None = None


@lru_cache(maxsize=1)
def get_reader():
    import easyocr

    model_dir = Path(os.environ.get("OCR_MODEL_DIR", "data/models"))
    model_dir.mkdir(parents=True, exist_ok=True)
    network_dir = model_dir / "user_network"
    return easyocr.Reader(
        ["bn", "en"],
        gpu=False,
        model_storage_directory=str(model_dir.resolve()),
        user_network_directory=str(network_dir.resolve()),
        verbose=False,
    )


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def parse_results(items: list) -> OcrResult:
    lines = []
    for item in items:
        if len(item) < 3:
            continue
        box, text, confidence = item[:3]
        cleaned = normalize_text(str(text))
        if not cleaned:
            continue
        try:
            serializable_box = [[float(point[0]), float(point[1])] for point in box]
            top = min(point[1] for point in serializable_box)
            left = min(point[0] for point in serializable_box)
            score = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError, IndexError):
            continue
        lines.append({"box": serializable_box, "text": cleaned, "raw_text": str(text), "confidence": score, "top": top, "left": left})
    lines.sort(key=lambda line: (round(line["top"] / 12), line["left"], line["top"]))
    text = "\n".join(line["text"] for line in lines)
    confidence = sum(line["confidence"] for line in lines) / len(lines) if lines else None
    raw = [{"box": line["box"], "text": line["raw_text"], "confidence": line["confidence"]} for line in lines]
    return OcrResult(text=text, confidence=confidence, raw_result_json=json.dumps(raw, ensure_ascii=False))


def preprocess_image(path: Path):
    import numpy as np

    with Image.open(path) as image:
        image = ImageOps.grayscale(image)
        if image.width < 1600:
            image = image.resize((image.width * 2, image.height * 2))
        image = ImageEnhance.Contrast(image).enhance(1.8)
        return np.array(image)


def extract_text(path: Path, min_confidence: float) -> OcrResult:
    if os.environ.get("OCR_ENABLED", "true").strip().casefold() in {"false", "0", "no"}:
        return OcrResult(text="", confidence=None, raw_result_json="[]", error_code="OCR_UNAVAILABLE")
    try:
        reader = get_reader()
        first = parse_results(reader.readtext(str(path), detail=1, paragraph=False))
    except Exception:
        return OcrResult(text="", confidence=None, raw_result_json="[]", error_code="OCR_UNAVAILABLE")
    if first.text and first.confidence is not None and first.confidence >= min_confidence:
        return first
    try:
        second = parse_results(reader.readtext(preprocess_image(path), detail=1, paragraph=False))
        if second.text and (not first.text or (second.confidence or 0) > (first.confidence or 0)):
            return second
        return first
    except Exception:
        return first
