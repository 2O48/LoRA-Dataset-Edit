from __future__ import annotations

import json
import math
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from dataset_paths import DATASETS_DIR, EXPORTS_DIR
from dataset_workspace import CONTROL_ROLES, _resolve_user_path


APP_STATE_DIR = DATASETS_DIR


def _clean_name(value: str, fallback: str = "untitled") -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", value or fallback).strip()
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or fallback


def _unique_name(name: str, used: set[str]) -> str:
    base = _clean_name(Path(name).stem)
    if base not in used:
        used.add(base)
        return base
    index = 2
    while True:
        candidate = f"{base}_{index}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def _target_size_for(source_size: tuple[int, int], target_pixels: int, multiple: int) -> tuple[int, int]:
    width, height = source_size
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image size.")
    multiple = max(1, int(multiple or 1))
    target_pixels = max(1, int(target_pixels or 1_000_000))
    aspect = width / height
    raw_width = math.sqrt(target_pixels * aspect)
    raw_height = raw_width / aspect
    target_width = max(multiple, int(round(raw_width / multiple)) * multiple)
    target_height = max(multiple, int(round(raw_height / multiple)) * multiple)
    while target_width * target_height > target_pixels and (target_width > multiple or target_height > multiple):
        if target_width / target_height > aspect and target_width > multiple:
            target_width -= multiple
        elif target_height > multiple:
            target_height -= multiple
        else:
            target_width -= multiple
    return target_width, target_height


def _resample_lanczos() -> int:
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


def _resize_center_crop(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")
    target_width, target_height = target_size
    width, height = image.size
    scale = max(target_width / width, target_height / height)
    resized_size = (max(target_width, math.ceil(width * scale)), max(target_height, math.ceil(height * scale)))
    resized = image.resize(resized_size, _resample_lanczos())
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _write_processed_image(source: Path, target: Path, target_size: tuple[int, int]):
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        processed = _resize_center_crop(image, target_size)
        if processed.mode == "RGBA":
            processed.save(target, format="PNG", optimize=True)
        else:
            processed.convert("RGB").save(target, format="PNG", optimize=True)


def _copy_original_image(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _active_control_roles(control_count: int) -> tuple[str, ...]:
    count = max(1, min(3, int(control_count or 1)))
    return CONTROL_ROLES[:count]


def _role_folder_name(export_prefix: str, role: str) -> str:
    return f"{export_prefix}_{role}"


def _role_folder(root: Path, export_prefix: str, role: str) -> Path:
    return root / _role_folder_name(export_prefix, role)


def _image_target_path(
    root: Path,
    export_prefix: str,
    base_name: str,
    source: Path,
    *,
    process_images: bool,
    role: str,
) -> Path:
    ext = ".png" if process_images else source.suffix.lower() or ".png"
    folder = _role_folder(root, export_prefix, role)
    return folder / f"{base_name}{ext}"


def _resolve_output_parent(value: str) -> Path:
    if (value or "").strip():
        return _resolve_user_path(value)
    return EXPORTS_DIR


def _build_export_root(output_parent: Path, export_name: str) -> Path:
    root = output_parent / export_name
    if not root.exists():
        return root
    index = 2
    while True:
        candidate = output_parent / f"{export_name}_{index}"
        if not candidate.exists():
            return candidate
        index += 1


def export_dataset(
    *,
    items: list[dict],
    output_format: str = "zip",
    output_dir: str = "",
    project_name: str = "",
    target_megapixels: float = 4.0,
    multiple: int = 16,
    process_images: bool = True,
    include_controls: bool = True,
    control_count: int = 1,
) -> dict:
    output_format = "folder" if output_format == "folder" else "zip"
    target_megapixels = max(1.0, min(4.0, float(target_megapixels or 4.0)))
    target_pixels = int(target_megapixels * 1_000_000)
    multiple = max(1, int(multiple or 16))
    if multiple not in {16, 32, 64}:
        raise ValueError("Size multiple must be 16, 32, or 64.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    clean_project_name = _clean_name(project_name, "dataset")
    export_prefix = f"{timestamp}_{clean_project_name}"
    export_name = export_prefix
    output_parent = _resolve_output_parent(output_dir)
    output_parent.mkdir(parents=True, exist_ok=True)
    export_root = _build_export_root(output_parent, export_name)
    export_root.mkdir(parents=True, exist_ok=True)

    control_roles = _active_control_roles(control_count) if include_controls else ()
    for role in (*control_roles, "result"):
        _role_folder(export_root, export_prefix, role).mkdir(parents=True, exist_ok=True)

    used_names: set[str] = set()
    exported = 0
    skipped: list[dict] = []
    manifest_items: list[dict] = []

    for item in items:
        paths = item.get("paths", {})
        source_value = paths.get("result", "")
        source = Path(source_value) if source_value else None
        if not source or not source.exists():
            skipped.append({"name": item.get("name", ""), "reason": "no result image"})
            continue

        base_name = _unique_name(str(item.get("name") or source.stem), used_names)
        target_size: Optional[tuple[int, int]] = None
        if process_images:
            with Image.open(source) as image:
                target_size = _target_size_for(image.size, target_pixels, multiple)
            image_target = _image_target_path(export_root, export_prefix, base_name, source, process_images=True, role="result")
            _write_processed_image(source, image_target, target_size)
        else:
            image_target = _image_target_path(export_root, export_prefix, base_name, source, process_images=False, role="result")
            _copy_original_image(source, image_target)

        text_target = _role_folder(export_root, export_prefix, "result") / f"{base_name}.txt"
        text_target.write_text(str(item.get("text") or "").strip(), encoding="utf-8")

        exported_roles = {"result": str(image_target.relative_to(export_root))}
        if include_controls:
            for role in control_roles:
                value = paths.get(role, "")
                if not value:
                    continue
                role_source = Path(value)
                if not role_source.exists():
                    continue
                role_target = _image_target_path(
                    export_root,
                    export_prefix,
                    base_name,
                    role_source,
                    process_images=process_images,
                    role=role,
                )
                if process_images and target_size:
                    _write_processed_image(role_source, role_target, target_size)
                else:
                    _copy_original_image(role_source, role_target)
                exported_roles[role] = str(role_target.relative_to(export_root))

        exported += 1
        manifest_items.append(
            {
                "name": item.get("name", ""),
                "export_name": base_name,
                "caption_source": item.get("caption_source", ""),
                "files": exported_roles,
                "caption": str(text_target.relative_to(export_root)),
                "target_size": list(target_size) if target_size else None,
            }
        )

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_name": clean_project_name,
        "export_prefix": export_prefix,
        "exported": exported,
        "skipped": skipped,
        "options": {
            "format": output_format,
            "process_images": process_images,
            "target_megapixels": target_megapixels,
            "multiple": multiple,
            "include_controls": include_controls,
            "control_count": control_count,
        },
        "items": manifest_items,
    }
    (export_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if output_format == "folder":
        return {
            "format": "folder",
            "path": str(export_root),
            "exported": exported,
            "skipped": skipped,
        }

    zip_path = export_root.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in sorted((path for path in export_root.rglob("*") if path.is_dir()), key=lambda path: str(path)):
            archive.write(directory, directory.relative_to(export_root))
        for file in sorted(export_root.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(export_root))
    return {
        "format": "zip",
        "path": str(zip_path),
        "filename": zip_path.name,
        "bytes": zip_path.read_bytes(),
        "exported": exported,
        "skipped": skipped,
    }
