"""Create the short, captioned FreshSense public-beta walkthrough video."""

from __future__ import annotations

import argparse
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


WIDTH = 1280
HEIGHT = 720
FPS = 15
BACKGROUND = (246, 247, 242)
INK = (23, 32, 25)
GREEN = (41, 77, 49)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "seguisb.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size=size)


def _cover(image: Image.Image, size: tuple[int, int], scale: float = 1.0) -> Image.Image:
    source = image.convert("RGB")
    factor = max(size[0] / source.width, size[1] / source.height) * scale
    resized = source.resize(
        (int(source.width * factor), int(source.height * factor)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, (resized.height - size[1]) // 2)
    return resized.crop((left, top, left + size[0], top + size[1]))


def _caption(frame: Image.Image, title: str, detail: str) -> Image.Image:
    output = frame.copy()
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rounded_rectangle((54, 500, 1226, 670), radius=24, fill=(246, 247, 242, 238))
    draw.text((86, 526), title, font=_font(42, bold=True), fill=INK)
    draw.text((88, 590), detail, font=_font(24), fill=(78, 91, 81))
    return output


def _title_card(title: str, detail: str, *, dark: bool = False) -> Image.Image:
    color = GREEN if dark else BACKGROUND
    image = Image.new("RGB", (WIDTH, HEIGHT), color)
    draw = ImageDraw.Draw(image)
    title_color = (255, 255, 255) if dark else INK
    detail_color = (216, 226, 216) if dark else (78, 91, 81)
    draw.text((84, 220), title, font=_font(64, bold=True), fill=title_color)
    draw.multiline_text(
        (88, 326), detail, font=_font(30), fill=detail_color, spacing=14
    )
    return image


def build_video(hero: Path, desktop: Path, output: Path) -> None:
    hero_image = Image.open(hero)
    desktop_image = Image.open(desktop)
    writer = imageio_ffmpeg.write_frames(
        str(output),
        (WIDTH, HEIGHT),
        fps=FPS,
        codec="libx264",
        quality=7,
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        macro_block_size=2,
    )
    writer.send(None)
    try:
        scenes: list[tuple[Image.Image, float]] = [
            (
                _title_card(
                    "FreshSense AI 0.5.1",
                    "A downloadable Windows public beta\nfor visible fruit-freshness guidance",
                ),
                5,
            ),
            (
                _caption(
                    _cover(ImageEnhance.Contrast(hero_image).enhance(1.02), (WIDTH, HEIGHT)),
                    "Start with one clear fruit photo",
                    "FreshSense currently supports apple, banana, and orange.",
                ),
                6,
            ),
            (
                _caption(
                    _cover(desktop_image, (WIDTH, HEIGHT), scale=1.08),
                    "Analyze visible freshness patterns",
                    "The supported-input gate can withhold unclear or unsupported photos.",
                ),
                7,
            ),
            (
                _caption(
                    _cover(desktop_image, (WIDTH, HEIGHT), scale=1.28),
                    "Review evidence and the next action",
                    "See confidence, risk guidance, storage advice, warnings, and Grad-CAM.",
                ),
                7,
            ),
            (
                _title_card(
                    "Private by default",
                    "Photos are not saved or uploaded automatically.\nDownload the beta from GitHub Releases.",
                    dark=True,
                ),
                5,
            ),
        ]
        for frame, seconds in scenes:
            for _ in range(round(seconds * FPS)):
                writer.send(frame.tobytes())
    finally:
        writer.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hero", required=True, type=Path)
    parser.add_argument("--desktop", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_video(args.hero, args.desktop, args.output)
    print(f"Beta walkthrough: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
