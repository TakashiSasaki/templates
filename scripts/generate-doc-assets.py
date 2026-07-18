#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = ROOT / "docs" / "assets" / "icons" / "icon-512.png"
OUTPUT_PATH = ROOT / "docs" / "assets" / "social" / "agent-policy-og.png"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        Path(
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def generate() -> None:
    width, height = 1200, 630
    top = (2, 38, 66)
    bottom = (6, 82, 110)
    image = Image.new("RGB", (width, height), top)
    pixels = image.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom, strict=True))
        for x in range(width):
            pixels[x, y] = color

    icon = Image.open(ICON_PATH).convert("RGBA").resize((430, 430), Image.Resampling.LANCZOS)
    image.paste(icon, (65, 100), icon)

    draw = ImageDraw.Draw(image)
    title_font = font(76, bold=True)
    subtitle_font = font(32)
    detail_font = font(25)
    white = (250, 252, 255)
    muted = (194, 222, 235)

    draw.text((545, 180), "agent-policy", font=title_font, fill=white)
    draw.text((550, 290), "Shared policy compiler", font=subtitle_font, fill=muted)
    draw.text((550, 342), "Reproducible agent instructions", font=subtitle_font, fill=muted)
    draw.rounded_rectangle(
        (548, 430, 1080, 486),
        radius=18,
        fill=(7, 65, 91),
        outline=(130, 205, 220),
        width=2,
    )
    draw.text((575, 444), "Policies  •  Bootstrap  •  Validation", font=detail_font, fill=white)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_PATH, format="PNG", optimize=True)


if __name__ == "__main__":
    generate()
