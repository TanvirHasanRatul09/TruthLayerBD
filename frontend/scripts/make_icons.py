"""Generate the PWA icons with Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


out = Path(__file__).resolve().parents[1] / "public" / "icons"
out.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    image = Image.new("RGB", (size, size), "#123d34")
    draw = ImageDraw.Draw(image)
    inset = round(size * 0.18)
    draw.rounded_rectangle((inset, inset, size - inset, size - inset), radius=round(size * 0.11), fill="#d6f3e8")
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", round(size * 0.40))
    bounds = draw.textbbox((0, 0), "T", font=font)
    x = (size - (bounds[2] - bounds[0])) / 2 - bounds[0]
    y = (size - (bounds[3] - bounds[1])) / 2 - bounds[1]
    draw.text((x, y), "T", font=font, fill="#123d34")
    image.save(out / f"icon-{size}.png", optimize=True)
