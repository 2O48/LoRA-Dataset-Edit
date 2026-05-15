from __future__ import annotations

import math
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageOps

MAX_CAPTION_PIXELS = 2_000_000


def _resample_lanczos() -> int:
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


def _needs_resize(width: int, height: int, max_pixels: int) -> bool:
    return width > 0 and height > 0 and (width * height) > max_pixels


def _target_size(width: int, height: int, max_pixels: int) -> tuple[int, int]:
    scale = math.sqrt(float(max_pixels) / float(width * height))
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    while new_w * new_h > max_pixels:
        if new_w >= new_h and new_w > 1:
            new_w -= 1
        elif new_h > 1:
            new_h -= 1
        else:
            break
    return new_w, new_h


def _should_keep_alpha(img: Image.Image) -> bool:
    if img.mode in {"RGBA", "LA"}:
        return True
    if img.mode == "P":
        return "transparency" in img.info
    return False


@contextmanager
def prepare_caption_images(
    image_paths: list[str],
    *,
    max_pixels: int = MAX_CAPTION_PIXELS,
) -> Iterator[list[str]]:
    prepared: list[str] = []
    temp_paths: list[Path] = []
    resample = _resample_lanczos()

    try:
        for raw_path in image_paths:
            src_path = Path(raw_path)
            with Image.open(src_path) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                if not _needs_resize(width, height, max_pixels):
                    prepared.append(str(src_path))
                    continue

                new_size = _target_size(width, height, max_pixels)
                resized = img.resize(new_size, resample)
                keep_alpha = _should_keep_alpha(resized)

                if keep_alpha:
                    suffix = ".png"
                    save_img = resized if resized.mode in {"RGBA", "LA"} else resized.convert("RGBA")
                    save_kwargs = {"format": "PNG", "optimize": True}
                else:
                    suffix = ".jpg"
                    save_img = resized.convert("RGB")
                    save_kwargs = {"format": "JPEG", "quality": 92, "optimize": True}

                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    temp_path = Path(tmp.name)
                save_img.save(temp_path, **save_kwargs)
                temp_paths.append(temp_path)
                prepared.append(str(temp_path))

        yield prepared
    finally:
        for path in temp_paths:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
