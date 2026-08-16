from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}


@dataclass(frozen=True)
class SavedImage:
    ref: str
    path: Path


async def save_private_photo(upload: UploadFile, media_dir: Path) -> str:
    image = await read_uploaded_image(upload)
    if min(image.size) < 384 or max(image.size) > 4096:
        raise ValueError("Use an image between 384 px and 4096 px on each side")
    relative = Path("profile") / f"{uuid4()}.jpg"
    destination = media_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "JPEG", quality=92, optimize=True)
    return f"/media/{relative.as_posix()}"


async def save_capture(upload: UploadFile, media_dir: Path, look_id: str) -> SavedImage:
    image = await read_uploaded_image(upload)
    if min(image.size) < 64 or max(image.size) > 4096:
        raise ValueError("Use a capture between 64 px and 4096 px on each side")
    relative = Path("looks") / look_id / "capture.jpg"
    destination = media_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "JPEG", quality=92, optimize=True)
    return SavedImage(ref=f"/media/{relative.as_posix()}", path=destination)


async def read_uploaded_image(upload: UploadFile) -> Image.Image:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Use a JPEG or PNG image")
    payload = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be smaller than 10 MB")
    try:
        with Image.open(BytesIO(payload)) as source:
            return ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("The uploaded file is not a readable image") from error
