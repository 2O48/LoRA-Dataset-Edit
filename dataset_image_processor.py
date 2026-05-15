from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from PIL import Image

from dataset_exporter import (
    _active_control_roles,
    _build_export_root,
    _clean_name,
    _copy_original_image,
    _image_target_path,
    _role_folder,
    _target_size_for,
    _unique_name,
    _write_processed_image,
)
from dataset_paths import TMP_DIR
from dataset_workspace import APP_STATE_DIR, CONTROL_ROLES, IMAGE_ROLES, _resolve_user_path


PROCESSED_DIR = TMP_DIR / "processed"
VIEWER_PROCESS_DIR = TMP_DIR / "viewer"


def _resolve_output_parent(value: str) -> Path:
    if (value or "").strip():
        return _resolve_user_path(value)
    return PROCESSED_DIR


def _viewer_process_root(name: str, operation: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    clean_name = _clean_name(name, "item")
    root = VIEWER_PROCESS_DIR / f"{timestamp}_{clean_name}_{operation}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _viewer_target_path(root: Path, role: str, name: str) -> Path:
    return root / role / f"{_clean_name(name, 'item')}.png"


def _item_active_roles(control_count: int) -> tuple[str, ...]:
    count = max(1, min(3, int(control_count or 1)))
    return (*CONTROL_ROLES[:count], "result")


def process_viewer_item_scale(*, item: dict, target_megapixels: float, control_count: int = 1) -> dict:
    target_megapixels = max(0.1, min(64.0, float(target_megapixels or 4.0)))
    target_pixels = int(target_megapixels * 1_000_000)
    root = _viewer_process_root(str(item.get("name", "") or "item"), "scale")
    paths = item.get("paths", {}) if isinstance(item.get("paths"), dict) else {}
    output_paths: dict[str, str] = {}
    target_sizes: dict[str, list[int]] = {}

    for role in _item_active_roles(control_count):
        source_value = paths.get(role, "")
        if not source_value:
            continue
        source = Path(source_value)
        if not source.is_file():
            continue
        with Image.open(source) as image:
            target_size = _target_size_for(image.size, target_pixels, 16)
        target = _viewer_target_path(root, role, str(item.get("name", "") or source.stem))
        _write_processed_image(source, target, target_size)
        output_paths[role] = str(target)
        target_sizes[role] = [target_size[0], target_size[1]]

    if "result" in output_paths:
        text = str(item.get("text", "") or "").strip()
        if text:
            Path(output_paths["result"]).with_suffix(".txt").write_text(text, encoding="utf-8")
    if not output_paths:
        raise ValueError("当前条目没有可处理的图像。")
    return {"path": str(root), "paths": output_paths, "target_sizes": target_sizes}


def process_viewer_item_match_result(*, item: dict, control_count: int = 1) -> dict:
    paths = item.get("paths", {}) if isinstance(item.get("paths"), dict) else {}
    result_source = Path(paths.get("result", "") or "")
    if not result_source.is_file():
        raise ValueError("当前条目缺少结果图，无法匹配结果图尺寸。")
    with Image.open(result_source) as result_image:
        target_size = result_image.size

    root = _viewer_process_root(str(item.get("name", "") or "item"), "match-result")
    output_paths: dict[str, str] = {}
    for role in CONTROL_ROLES[: max(1, min(3, int(control_count or 1)))]:
        source_value = paths.get(role, "")
        if not source_value:
            continue
        source = Path(source_value)
        if not source.is_file():
            continue
        target = _viewer_target_path(root, role, str(item.get("name", "") or source.stem))
        _write_processed_image(source, target, target_size)
        output_paths[role] = str(target)

    if not output_paths:
        raise ValueError("当前条目没有可匹配的控制图。")
    return {"path": str(root), "paths": output_paths, "target_size": [target_size[0], target_size[1]]}


def process_workspace_images(
    *,
    items: list[dict],
    output_dir: str = "",
    project_name: str = "",
    target_megapixels: float = 4.0,
    multiple: int = 16,
    include_controls: bool = True,
    control_count: int = 1,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    target_megapixels = max(1.0, min(4.0, float(target_megapixels or 4.0)))
    target_pixels = int(target_megapixels * 1_000_000)
    multiple = max(1, int(multiple or 16))
    if multiple not in {16, 32, 64}:
        raise ValueError("Size multiple must be 16, 32, or 64.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    clean_project_name = _clean_name(project_name, "processed")
    process_prefix = f"{timestamp}_{clean_project_name}"
    output_parent = _resolve_output_parent(output_dir)
    output_parent.mkdir(parents=True, exist_ok=True)
    process_root = _build_export_root(output_parent, process_prefix)
    process_root.mkdir(parents=True, exist_ok=True)

    control_roles = _active_control_roles(control_count) if include_controls else ()
    active_roles = (*control_roles, "result")
    role_dirs = {
        role: _role_folder(process_root, process_prefix, role)
        for role in active_roles
    }
    for path in role_dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    used_names: set[str] = set()
    processed = 0
    skipped: list[dict] = []
    manifest_items: list[dict] = []
    total = len(items)
    done = 0

    def emit(current: str = "", level: str = "info", message: str = ""):
        if progress_callback is None:
            return
        progress_callback(
            {
                "total": total,
                "done": done,
                "processed": processed,
                "skipped": len(skipped),
                "current": current,
                "level": level,
                "message": message,
            }
        )

    emit(message="Image processing started")

    for item in items:
        current_name = str(item.get("name", "") or "")
        paths = item.get("paths", {})
        result_value = paths.get("result", "")
        result_source = Path(result_value) if result_value else None
        if not result_source or not result_source.exists():
            skipped.append({"name": item.get("name", ""), "reason": "no result image"})
            done += 1
            emit(current_name, "warn", "Skipped item without result image")
            continue

        try:
            base_name = _unique_name(str(item.get("name") or result_source.stem), used_names)
            with Image.open(result_source) as image:
                target_size = _target_size_for(image.size, target_pixels, multiple)

            result_target = _image_target_path(
                process_root,
                process_prefix,
                base_name,
                result_source,
                process_images=True,
                role="result",
            )
            _write_processed_image(result_source, result_target, target_size)
            text_target = role_dirs["result"] / f"{base_name}.txt"
            text_target.write_text(str(item.get("text") or "").strip(), encoding="utf-8")

            processed_files = {
                "result": str(result_target.relative_to(process_root)),
                "caption": str(text_target.relative_to(process_root)),
            }

            for role in control_roles:
                value = paths.get(role, "")
                if not value:
                    continue
                role_source = Path(value)
                if not role_source.exists():
                    continue
                role_target = _image_target_path(
                    process_root,
                    process_prefix,
                    base_name,
                    role_source,
                    process_images=True,
                    role=role,
                )
                _write_processed_image(role_source, role_target, target_size)
                processed_files[role] = str(role_target.relative_to(process_root))

            processed += 1
            manifest_items.append(
                {
                    "name": item.get("name", ""),
                    "processed_name": base_name,
                    "caption_source": item.get("caption_source", ""),
                    "files": processed_files,
                    "target_size": list(target_size),
                }
            )
            done += 1
            emit(current_name, "ok", f"Processed {base_name}")
        except Exception as exc:
            skipped.append({"name": item.get("name", ""), "reason": str(exc)})
            done += 1
            emit(current_name, "error", str(exc))

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_name": clean_project_name,
        "process_prefix": process_prefix,
        "processed": processed,
        "skipped": skipped,
        "options": {
            "target_megapixels": target_megapixels,
            "multiple": multiple,
            "include_controls": include_controls,
            "control_count": control_count,
        },
        "items": manifest_items,
    }
    (process_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    dirs = {role: str(path) for role, path in role_dirs.items()}
    return {
        "path": str(process_root),
        "project_name": clean_project_name,
        "process_prefix": process_prefix,
        "dirs": dirs,
        "processed": processed,
        "skipped": skipped,
    }


def process_workspace_match_results(
    *,
    items: list[dict],
    output_dir: str = "",
    project_name: str = "",
    include_controls: bool = True,
    only_mismatched: bool = True,
    control_count: int = 1,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    clean_project_name = _clean_name(project_name, "matched")
    process_prefix = f"{timestamp}_{clean_project_name}_matched"
    output_parent = _resolve_output_parent(output_dir)
    output_parent.mkdir(parents=True, exist_ok=True)
    process_root = _build_export_root(output_parent, process_prefix)
    process_root.mkdir(parents=True, exist_ok=True)

    control_roles = _active_control_roles(control_count) if include_controls else ()
    active_roles = (*control_roles, "result")
    role_dirs = {role: _role_folder(process_root, process_prefix, role) for role in active_roles}
    for path in role_dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    used_names: set[str] = set()
    processed = 0
    skipped: list[dict] = []
    manifest_items: list[dict] = []
    total = len(items)
    done = 0

    def emit(current: str = "", level: str = "info", message: str = ""):
        if progress_callback is None:
            return
        progress_callback(
            {
                "total": total,
                "done": done,
                "processed": processed,
                "skipped": len(skipped),
                "current": current,
                "level": level,
                "message": message,
            }
        )

    emit(message="Match-result processing started")

    for item in items:
        current_name = str(item.get("name", "") or "")
        paths = item.get("paths", {})
        result_value = paths.get("result", "")
        result_source = Path(result_value) if result_value else None
        if not result_source or not result_source.exists():
            skipped.append({"name": item.get("name", ""), "reason": "no result image"})
            done += 1
            emit(current_name, "warn", "Skipped item without result image")
            continue

        try:
            base_name = _unique_name(str(item.get("name") or result_source.stem), used_names)
            with Image.open(result_source) as image:
                target_size = image.size

            result_target = _image_target_path(
                process_root,
                process_prefix,
                base_name,
                result_source,
                process_images=False,
                role="result",
            )
            _copy_original_image(result_source, result_target)
            text_target = role_dirs["result"] / f"{base_name}.txt"
            text_target.write_text(str(item.get("text") or "").strip(), encoding="utf-8")

            processed_files = {
                "result": str(result_target.relative_to(process_root)),
                "caption": str(text_target.relative_to(process_root)),
            }

            resized_controls = 0
            copied_controls = 0
            for role in control_roles:
                value = paths.get(role, "")
                if not value:
                    continue
                role_source = Path(value)
                if not role_source.exists():
                    continue
                with Image.open(role_source) as role_image:
                    role_size = role_image.size
                needs_resize = role_size != target_size
                role_target = _image_target_path(
                    process_root,
                    process_prefix,
                    base_name,
                    role_source,
                    process_images=needs_resize or not only_mismatched,
                    role=role,
                )
                if only_mismatched and not needs_resize:
                    _copy_original_image(role_source, role_target)
                    copied_controls += 1
                else:
                    _write_processed_image(role_source, role_target, target_size)
                    resized_controls += 1
                processed_files[role] = str(role_target.relative_to(process_root))

            processed += 1
            manifest_items.append(
                {
                    "name": item.get("name", ""),
                    "processed_name": base_name,
                    "caption_source": item.get("caption_source", ""),
                    "files": processed_files,
                    "target_size": [target_size[0], target_size[1]],
                    "resized_controls": resized_controls,
                    "copied_controls": copied_controls,
                }
            )
            done += 1
            if only_mismatched:
                emit(current_name, "ok", f"Matched {base_name} · resized {resized_controls} · copied {copied_controls}")
            else:
                emit(current_name, "ok", f"Matched {base_name}")
        except Exception as exc:
            skipped.append({"name": item.get("name", ""), "reason": str(exc)})
            done += 1
            emit(current_name, "error", str(exc))

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_name": clean_project_name,
        "process_prefix": process_prefix,
        "processed": processed,
        "skipped": skipped,
        "options": {
            "mode": "match_result_size",
            "include_controls": include_controls,
            "only_mismatched": only_mismatched,
            "control_count": control_count,
        },
        "items": manifest_items,
    }
    (process_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    dirs = {role: str(path) for role, path in role_dirs.items()}
    return {
        "path": str(process_root),
        "project_name": clean_project_name,
        "process_prefix": process_prefix,
        "dirs": dirs,
        "processed": processed,
        "skipped": skipped,
    }
