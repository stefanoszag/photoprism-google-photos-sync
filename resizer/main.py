"""Resize images in the shared folder before upload."""

import logging
import mimetypes
from pathlib import Path

from PIL import Image, ImageOps

from . import config

logger = logging.getLogger(__name__)

# Prefer Pillow 10+ Resampling enum; fallback for older versions
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.LANCZOS


def _is_image(path: Path) -> bool:
    """Return True if the file path has an image MIME type."""
    mime_type, _ = mimetypes.guess_type(str(path))
    return bool(mime_type and mime_type.startswith("image/"))


def _list_image_paths(folder_path: str) -> list[Path]:
    """List paths of image files in the folder (same criteria as uploader)."""
    folder = Path(folder_path)
    if not folder.is_dir():
        return []
    return [p for p in folder.iterdir() if p.is_file() and _is_image(p)]


def _resize_one(file_path: Path, percentage: int) -> bool:
    """
    Resize a single image in place. Preserves aspect ratio and format.

    Returns:
        True if resized successfully, False on error or skip.
    """
    try:
        with Image.open(file_path) as img:
            # Apply EXIF orientation so portrait/landscape is correct (many cameras store
            # orientation in metadata only; without this, portrait photos can appear landscape).
            img = ImageOps.exif_transpose(img)

            # Skip if not needing resize
            w, h = img.size
            new_w = max(1, int(w * percentage / 100))
            new_h = max(1, int(h * percentage / 100))
            if (new_w, new_h) == (w, h):
                logger.debug("Skip %s: already at or below target size", file_path.name)
                return True  # count as processed, no error

            # Convert RGBA/P to RGB for JPEG if needed; otherwise keep mode
            out = img.resize((new_w, new_h), _RESAMPLE)
            if out.mode in ("RGBA", "P") and file_path.suffix.lower() in (".jpg", ".jpeg"):
                out = out.convert("RGB")

            save_kwargs = {}
            if out.format == "JPEG" or file_path.suffix.lower() in (".jpg", ".jpeg"):
                save_kwargs["quality"] = 92
            elif out.format == "PNG":
                save_kwargs["optimize"] = True

            out.save(str(file_path), **save_kwargs)
            logger.debug("Resized %s from %dx%d to %dx%d", file_path.name, w, h, new_w, new_h)
            return True
    except Exception as e:
        logger.warning("Failed to resize %s: %s", file_path.name, e)
        return False


def resize_images() -> dict:
    """
    Resize images in the shared folder according to configuration.

    Images are scaled by RESIZE_PERCENTAGE (e.g. 80 = 80% of original dimensions).
    Aspect ratio and original format are preserved. Files are overwritten in place.

    Returns:
        dict: Statistics with keys "processed", "skipped", "errors". Empty dict if disabled.
    """
    if not config.RESIZE_ENABLED:
        logger.info("Resize is disabled (RESIZE_ENABLED=false). Skipping.")
        return {}

    if config.RESIZE_PERCENTAGE >= 100:
        logger.info(
            "Resize percentage is %d (>= 100). No resizing needed.",
            config.RESIZE_PERCENTAGE,
        )
        return {}

    folder = Path(config.SHARED_FOLDER)
    if not folder.exists():
        logger.warning("Shared folder does not exist: %s. Skipping resize.", config.SHARED_FOLDER)
        return {"processed": 0, "skipped": 0, "errors": 0}

    paths = _list_image_paths(config.SHARED_FOLDER)
    if not paths:
        logger.info("No images found in %s. Nothing to resize.", config.SHARED_FOLDER)
        return {"processed": 0, "skipped": 0, "errors": 0}

    logger.info(
        "Resizing %d image(s) to %d%% in %s",
        len(paths),
        config.RESIZE_PERCENTAGE,
        config.SHARED_FOLDER,
    )

    processed = 0
    errors = 0
    for path in paths:
        if _resize_one(path, config.RESIZE_PERCENTAGE):
            processed += 1
        else:
            errors += 1

    logger.info("Resize complete: %d processed, %d errors", processed, errors)
    return {"processed": processed, "skipped": 0, "errors": errors}
