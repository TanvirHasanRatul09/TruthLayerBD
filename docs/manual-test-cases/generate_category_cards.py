"""Regenerate clearly synthetic OCR cards from category-evaluation.json."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "category-evaluation.json").read_text(encoding="utf-8"))
OUTPUT = HERE / "category-cards"
OUTPUT.mkdir(exist_ok=True)
FONT = "C:/Windows/Fonts/Nirmala.ttf"
if not Path(FONT).exists():
    raise SystemExit("Nirmala.ttf is required to render the Bangla test cards on Windows.")


def lines(draw, value, font, width):
    result = []
    current = ""
    for word in value.split():
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > width:
            result.append(current)
            current = word
        else:
            current = trial
    if current:
        result.append(current)
    return result


for case in CASES:
    canvas = Image.new("RGB", (1200, 630), "#26142f")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((32, 32, 1168, 598), 26, fill="#392047", outline="#bd8bd4", width=3)
    eyebrow = ImageFont.truetype(FONT, 29)
    headline = ImageFont.truetype(FONT, 58 if case["language"] == "en" else 54)
    note = ImageFont.truetype(FONT, 24)
    draw.text((70, 68), "TRUTHLAYER BD  /  SYNTHETIC TEST CARD", font=eyebrow, fill="#ddb5ee")
    y = 175
    for line in lines(draw, case["claim"], headline, 1050):
        draw.text((70, y), line, font=headline, fill="#fff4ff")
        y += 88
    if case.get("claimed_publisher"):
        draw.text((70, 488), f"CLAIMED SOURCE: {case['claimed_publisher']}", font=note, fill="#e9c7f2")
    draw.text((70, 548), "LOCALLY GENERATED TEST IMAGE  •  NOT A REAL NEWS POST", font=note, fill="#d6adc9")
    canvas.save(OUTPUT / f"{case['id']}.png", optimize=True)

print(f"Generated {len(CASES)} cards in {OUTPUT}")
