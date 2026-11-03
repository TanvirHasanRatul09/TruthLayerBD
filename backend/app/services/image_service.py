from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings

IMAGE_TYPES = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}
MAX_IMAGE_PIXELS = 50_000_000


async def store_image(file: UploadFile, settings: Settings) -> tuple[str, Path]:
    if file.content_type not in {item[0] for item in IMAGE_TYPES.values()}:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WebP images are supported.")

    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Image file is empty.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="Image exceeds the upload size limit.")

    try:
        with Image.open(BytesIO(data)) as image:
            image_format = image.format
            if image_format not in IMAGE_TYPES:
                raise HTTPException(status_code=415, detail="Unsupported image signature.")
            expected_type, extension = IMAGE_TYPES[image_format]
            if file.content_type != expected_type:
                raise HTTPException(status_code=415, detail="Image type does not match its contents.")
            if image.width < 1 or image.height < 1 or image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=422, detail="Image dimensions are invalid or too large.")
            image.verify()
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status_code=422, detail="Image is corrupt or unreadable.") from None

    analysis_id = f"an_{uuid4().hex}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{analysis_id}{extension}"
    path.write_bytes(data)
    return analysis_id, path


def find_image(analysis_id: str, settings: Settings) -> Path | None:
    if not analysis_id.startswith("an_") or len(analysis_id) != 35:
        return None
    suffix = analysis_id[3:]
    if any(character not in "0123456789abcdef" for character in suffix):
        return None
    upload_dir = Path(settings.upload_dir)
    for _, extension in IMAGE_TYPES.values():
        path = upload_dir / f"{analysis_id}{extension}"
        if path.is_file():
            return path
    return None
