"""Deterministic synthetic unsupported-image stress cases.

These inputs are regression tests, not a substitute for independently collected
real-world unsupported photographs.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
from PIL import Image, ImageDraw


def synthetic_ood_cases(count: int = 192, *, seed: int = 20260717) -> Iterator[tuple[str, Image.Image]]:
    if count < 1:
        return
    rng = np.random.default_rng(seed)
    families = (
        "noise",
        "checkerboard",
        "stripes",
        "gradient",
        "geometric_shapes",
        "text_like",
    )
    for index in range(count):
        family = families[index % len(families)]
        array = _render_case(family, index, rng)
        yield f"synthetic_{family}_{index:04d}", Image.fromarray(array, mode="RGB")


def _render_case(family: str, index: int, rng: np.random.Generator) -> np.ndarray:
    height = width = 224
    if family == "noise":
        return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)

    if family == "checkerboard":
        cell = 2 + (index % 22)
        yy, xx = np.indices((height, width))
        mask = ((xx // cell + yy // cell) % 2).astype(np.uint8)
        colors = rng.integers(0, 256, (2, 3), dtype=np.uint8)
        return colors[mask]

    if family == "stripes":
        period = 3 + (index % 29)
        array = np.zeros((height, width, 3), dtype=np.uint8)
        color_a = rng.integers(0, 256, 3, dtype=np.uint8)
        color_b = rng.integers(0, 256, 3, dtype=np.uint8)
        if index % 2:
            mask = (np.arange(width) // period) % 2
            array[:] = np.where(mask[None, :, None] == 0, color_a, color_b)
        else:
            mask = (np.arange(height) // period) % 2
            array[:] = np.where(mask[:, None, None] == 0, color_a, color_b)
        return array

    if family == "gradient":
        start = rng.integers(0, 128, 3)
        end = rng.integers(128, 256, 3)
        values = np.linspace(start, end, width, dtype=np.float32)
        if index % 2:
            values = values[::-1]
        return np.tile(values[None, :, :], (height, 1, 1)).astype(np.uint8)

    background = tuple(int(value) for value in rng.integers(20, 236, 3))
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    if family == "geometric_shapes":
        for _ in range(4 + (index % 9)):
            x1, x2 = sorted(int(value) for value in rng.integers(0, width, 2))
            y1, y2 = sorted(int(value) for value in rng.integers(0, height, 2))
            color = tuple(int(value) for value in rng.integers(0, 256, 3))
            if rng.random() < 0.5:
                draw.rectangle((x1, y1, x2, y2), fill=color, outline=(255, 255, 255))
            else:
                draw.ellipse((x1, y1, x2, y2), fill=color, outline=(0, 0, 0))
    else:
        for row in range(10, height - 10, 18):
            length = int(rng.integers(width // 4, width - 20))
            color = tuple(int(value) for value in rng.integers(0, 256, 3))
            draw.rectangle((10, row, length, row + 6), fill=color)
    return np.asarray(image, dtype=np.uint8)
