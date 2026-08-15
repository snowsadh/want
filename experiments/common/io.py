from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")


def normalized_image(path: Path) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    if min(image.size) < 128 or max(image.size) > 4096:
        raise ValueError(f"Unsupported image dimensions {image.size} for {path.name}")
    return image


def save_lens_crop(image: Image.Image, path: Path, max_bytes: int = 490_000) -> Path:
    """Save a crop below SerpApi's documented 500 KB upload limit."""
    ensure_dir(path.parent)
    working = image.copy()
    for max_side in (1600, 1280, 1024, 800, 640):
        candidate = working.copy()
        candidate.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        for quality in (90, 82, 74, 66, 58):
            candidate.save(path, "JPEG", quality=quality, optimize=True)
            if path.stat().st_size <= max_bytes:
                return path
    raise ValueError(f"Could not encode {path.name} below {max_bytes} bytes")
