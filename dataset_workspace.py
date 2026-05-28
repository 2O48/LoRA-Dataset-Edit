from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import threading
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from pathlib import Path
from typing import Optional

from PIL import Image
from dataset_paths import DATASETS_DIR, WORKSPACES_DIR

try:
    import send2trash
except Exception:
    send2trash = None


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".avif"}
IMAGE_ROLES = ("control1", "control2", "control3", "result")
CONTROL_ROLES = ("control1", "control2", "control3")
INVALID_BASENAME_CHARS = set('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}
APP_STATE_DIR = DATASETS_DIR
WORKSPACE_STATE_DIR = WORKSPACES_DIR
ROLE_STRIP_PATTERNS = (
    r"(?:control|ctrl|guide|cond|conditioning|source|input)[\s._-]*1",
    r"(?:control|ctrl|guide|cond|conditioning|source|input)[\s._-]*2",
    r"(?:control|ctrl|guide|cond|conditioning|source|input)[\s._-]*3",
    r"(?:ref|reference)",
    r"(?:result|output|target|final|edited|edit|after|render|gt)",
    r"(?:控制图[\s._-]*1|控制1|控制图一)",
    r"(?:控制图[\s._-]*2|控制2|控制图二)",
    r"(?:控制图[\s._-]*3|控制3|控制图三)",
    r"(?:结果图|结果|输出图|输出)",
)


def _natural_key(value: str):
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", value)]


def _resolve_user_path(value: str) -> Path:
    raw = (value or "").strip()
    if not raw:
        return Path(raw)

    # Support Windows-style paths when the app is running under WSL/Linux.
    drive_match = re.match(r"^([a-zA-Z]):[\\/](.*)$", raw)
    if drive_match:
        if os.name == "nt":
            return Path(raw)
        drive = drive_match.group(1).lower()
        rest = drive_match.group(2).replace("\\", "/").strip("/")
        return Path("/mnt") / drive / rest

    # Support UNC-like slashes copied into the app, normalize backslashes.
    if "\\" in raw and "/" not in raw:
        raw = raw.replace("\\", "/")

    return Path(raw).expanduser()


def _parse_caption_segments(content: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"[,，;\n；]+", content or "") if segment.strip()]


def _parse_tags(content: str) -> list[str]:
    # Backward-compatible alias for previous tag-based data flow.
    return _parse_caption_segments(content)


def _normalize_segment_inputs(values: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for segment in _parse_caption_segments(str(raw or "")):
            key = segment.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(segment)
    return items


def _merge_text_with_segments(existing: str, segments: list[str], position: str = "after") -> str:
    clean_segments = _normalize_segment_inputs(segments)
    if not clean_segments:
        return existing
    current_text = (existing or "").strip()
    if not current_text:
        return ", ".join(clean_segments)
    current_segments = _parse_caption_segments(current_text)
    current_index = {segment.lower() for segment in current_segments}
    additions = [segment for segment in clean_segments if segment.lower() not in current_index]
    if not additions:
        return current_text
    if position == "before":
        return ", ".join(additions) + f"; {current_text.lstrip(',，;； ')}"
    return f"{current_text.rstrip(',，;； ')}; " + ", ".join(additions)


def _split_caption_parts(content: str) -> list[tuple[str, str]]:
    tokens = re.split(r"([,，;\n；]+)", content or "")
    parts: list[tuple[str, str]] = []
    index = 0
    while index < len(tokens):
        segment = tokens[index] if index < len(tokens) else ""
        separator = tokens[index + 1] if index + 1 < len(tokens) else ""
        index += 2
        if not segment or not segment.strip():
            if separator and parts:
                prev_segment, prev_separator = parts[-1]
                parts[-1] = (prev_segment, prev_separator + separator)
            continue
        parts.append((segment, separator))
    return parts


def _join_caption_parts(parts: list[tuple[str, str]]) -> str:
    return "".join(segment + separator for segment, separator in parts)


def _normalize_caption_spacing(content: str) -> str:
    compact = re.sub(r"\n[ \t]+", "\n", content or "")
    return compact.strip()


def _delete_caption_segments(content: str, needles: list[str]) -> str:
    if not needles:
        return content
    parts = _split_caption_parts(content)
    filtered = [
        (segment, separator)
        for segment, separator in parts
        if not any(needle in segment.strip().lower() for needle in needles)
    ]
    return _normalize_caption_spacing(_join_caption_parts(filtered))


def _replace_caption_segment(content: str, old_segment: str, new_segment: str) -> str:
    target = (old_segment or "").strip().lower()
    if not target:
        return content
    replacement = (new_segment or "").strip()
    changed = False
    updated_parts: list[tuple[str, str]] = []
    for segment, separator in _split_caption_parts(content):
        if segment.strip().lower() != target:
            updated_parts.append((segment, separator))
            continue
        changed = True
        if replacement:
            updated_parts.append((replacement, separator))
    if not changed:
        return content
    return _normalize_caption_spacing(_join_caption_parts(updated_parts))


def _send_to_trash(path: Path):
    if send2trash is not None:
        send2trash.send2trash(str(path))
    else:
        raise RuntimeError("send2trash is not available; refusing to permanently delete files.")


def _parse_ignore_tokens(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        source = value
    else:
        source = " ".join(str(item or "") for item in value)
    return [token.strip().lower() for token in re.split(r"[,;\n，\s]+", source) if token.strip()]


def _parse_rename_tokens(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        source = value
    else:
        source = " ".join(str(item or "") for item in value)
    return [token.strip() for token in re.split(r"[,;\n，]+", source) if token.strip()]


class DatasetWorkspace:
    def __init__(self):
        self._lock = threading.RLock()
        self.dirs: dict[str, Optional[Path]] = {role: None for role in IMAGE_ROLES}
        self.files: dict[str, dict[str, Path]] = {role: {} for role in IMAGE_ROLES}
        self.txt_files: dict[str, Path] = {}
        self.txt_content: dict[str, str] = {}
        self.caption_overrides: dict[str, str] = {}
        self.caption_deleted: set[str] = set()
        self.excluded_names: set[str] = set()
        self.file_names: list[str] = []
        self._image_sizes: dict[tuple[str, str], Optional[tuple[int, int]]] = {}
        self._resolution_mismatch: set[str] = set()
        self._resolution_index_ready = False
        self._global_segments_cache: list[dict] = []
        self._global_segments_dirty = True
        self.control_count = 1
        self.ignore_tokens: list[str] = []
        self.workspace_key = ""

    def open_dirs(
        self,
        *,
        control1_dir: Optional[str] = None,
        control2_dir: Optional[str] = None,
        control3_dir: Optional[str] = None,
        result_dir: Optional[str] = None,
        control_count: Optional[int] = None,
        ignore_tokens=None,
    ) -> dict:
        with self._lock:
            if control_count is not None:
                self.control_count = max(0, min(3, int(control_count)))
            if ignore_tokens is not None:
                self.ignore_tokens = _parse_ignore_tokens(ignore_tokens)

            for key, value in (
                ("control1", control1_dir),
                ("control2", control2_dir),
                ("control3", control3_dir),
                ("result", result_dir),
            ):
                if value is None:
                    continue
                raw_value = str(value or "").strip()
                if not raw_value:
                    self.dirs[key] = None
                    continue
                path = _resolve_user_path(raw_value)
                if not path.is_dir():
                    raise FileNotFoundError(f"{key} directory does not exist: {value}")
                self.dirs[key] = path

            scanned_images = {key: self._scan_images(self.dirs[key]) for key in IMAGE_ROLES}
            groups: dict[str, dict] = {}
            for role in IMAGE_ROLES:
                for raw_name, path in scanned_images[role].items():
                    match_key = self._normalize_match_key(raw_name)
                    group = groups.setdefault(match_key, {"paths": {}, "raw_names": {}, "txt_path": None, "txt_raw_name": ""})
                    current_name = group["raw_names"].get(role)
                    if current_name is None or _natural_key(raw_name) < _natural_key(current_name):
                        group["paths"][role] = path
                        group["raw_names"][role] = raw_name

            self.txt_files = {}
            self.txt_content = {}
            self.caption_overrides = {}
            self.caption_deleted = set()
            self.excluded_names = set()
            result_path = self.dirs["result"]
            if result_path and result_path.is_dir():
                for file in result_path.rglob("*.txt"):
                    if not file.is_file() or file.suffix.lower() != ".txt":
                        continue
                    raw_name = self._relative_stem(result_path, file)
                    match_key = self._normalize_match_key(raw_name)
                    group = groups.setdefault(match_key, {"paths": {}, "raw_names": {}, "txt_path": None, "txt_raw_name": ""})
                    current_name = group["txt_raw_name"]
                    if not current_name or _natural_key(raw_name) < _natural_key(current_name):
                        group["txt_path"] = file
                        group["txt_raw_name"] = raw_name

            self.files = {role: {} for role in IMAGE_ROLES}
            self.file_names = []
            used_names: set[str] = set()
            for _, group in sorted(groups.items(), key=lambda item: _natural_key(self._pick_display_name(item[1], item[0]))):
                display_name = self._ensure_unique_name(self._pick_display_name(group, ""), used_names)
                used_names.add(display_name)
                self.file_names.append(display_name)
                for role in IMAGE_ROLES:
                    path = group["paths"].get(role)
                    if path is not None:
                        self.files[role][display_name] = path
                txt_path = group.get("txt_path")
                if txt_path is not None:
                    self.txt_files[display_name] = txt_path
                    self.txt_content[display_name] = self._read_text_file(txt_path)

            self._image_sizes.clear()
            self._resolution_mismatch.clear()
            self._resolution_index_ready = False
            self.workspace_key = self._compute_workspace_key()
            self._load_workspace_state()
            self._apply_workspace_state()
            self._mark_global_segments_dirty()
            self.file_names = sorted(self.file_names, key=_natural_key)
            return self.get_workspace_summary()

    def merge_dirs(
        self,
        *,
        control1_dir: Optional[str] = None,
        control2_dir: Optional[str] = None,
        control3_dir: Optional[str] = None,
        result_dir: Optional[str] = None,
        control_count: Optional[int] = None,
    ) -> dict:
        with self._lock:
            if control_count is not None:
                self.control_count = max(0, min(3, int(control_count)))

            incoming_dirs: dict[str, Optional[Path]] = {role: None for role in IMAGE_ROLES}
            for key, value in (
                ("control1", control1_dir),
                ("control2", control2_dir),
                ("control3", control3_dir),
                ("result", result_dir),
            ):
                raw_value = str(value or "").strip()
                if not raw_value:
                    continue
                path = _resolve_user_path(raw_value)
                if not path.is_dir():
                    raise FileNotFoundError(f"{key} directory does not exist: {value}")
                incoming_dirs[key] = path

            if not any(incoming_dirs.values()):
                raise ValueError("Merge requires at least one image directory.")

            scanned_images = {key: self._scan_images(incoming_dirs[key]) for key in IMAGE_ROLES}
            groups: dict[str, dict] = {}
            for role in IMAGE_ROLES:
                for raw_name, path in scanned_images[role].items():
                    match_key = self._normalize_match_key(raw_name)
                    group = groups.setdefault(match_key, {"paths": {}, "raw_names": {}, "txt_path": None, "txt_raw_name": ""})
                    current_name = group["raw_names"].get(role)
                    if current_name is None or _natural_key(raw_name) < _natural_key(current_name):
                        group["paths"][role] = path
                        group["raw_names"][role] = raw_name

            result_path = incoming_dirs["result"]
            if result_path and result_path.is_dir():
                for file in result_path.rglob("*.txt"):
                    if not file.is_file() or file.suffix.lower() != ".txt":
                        continue
                    raw_name = self._relative_stem(result_path, file)
                    match_key = self._normalize_match_key(raw_name)
                    group = groups.setdefault(match_key, {"paths": {}, "raw_names": {}, "txt_path": None, "txt_raw_name": ""})
                    current_name = group["txt_raw_name"]
                    if not current_name or _natural_key(raw_name) < _natural_key(current_name):
                        group["txt_path"] = file
                        group["txt_raw_name"] = raw_name

            used_names = set(self.file_names) | set(self.excluded_names)
            merged_names: list[str] = []
            for _, group in sorted(groups.items(), key=lambda item: _natural_key(self._pick_display_name(item[1], item[0]))):
                display_name = self._ensure_unique_name(self._pick_display_name(group, ""), used_names)
                used_names.add(display_name)
                self.file_names.append(display_name)
                merged_names.append(display_name)
                for role in IMAGE_ROLES:
                    path = group["paths"].get(role)
                    if path is not None:
                        self.files[role][display_name] = path
                txt_path = group.get("txt_path")
                if txt_path is not None:
                    self.txt_files[display_name] = txt_path
                    self.txt_content[display_name] = self._read_text_file(txt_path)

            self._image_sizes.clear()
            self._resolution_mismatch.clear()
            self._resolution_index_ready = False
            self.file_names = sorted(self.file_names, key=_natural_key)
            self._mark_global_segments_dirty()
            summary = self.get_workspace_summary()
            return {
                "merged": len(merged_names),
                "names": merged_names,
                "workspace": summary,
            }

    def swap_control_result_pairs(
        self,
        *,
        control_dir: Optional[str] = None,
        result_dir: Optional[str] = None,
        suffix: str = "_swap",
    ) -> dict:
        with self._lock:
            control_root = _resolve_user_path(str(control_dir or self.dirs["control1"] or ""))
            result_root = _resolve_user_path(str(result_dir or self.dirs["result"] or ""))
            if not control_root.is_dir():
                raise FileNotFoundError(f"control directory does not exist: {control_dir or ''}")
            if not result_root.is_dir():
                raise FileNotFoundError(f"result directory does not exist: {result_dir or ''}")
            if control_root.resolve() == result_root.resolve():
                raise ValueError("Control and result directories must be different.")

            clean_suffix = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(suffix or "").strip()) or "_swap"
            control_images = self._scan_images(control_root)
            result_images = self._scan_images(result_root)
            control_groups = self._group_images_by_match_key(control_images)
            result_groups = self._group_images_by_match_key(result_images)
            matched_keys = sorted(set(control_groups) & set(result_groups), key=_natural_key)
            if not matched_keys:
                summary = self.get_workspace_summary()
                return {"swapped": 0, "created": [], "skipped": [], "workspace": summary}

            used_raw_names = set(control_images) | set(result_images)
            created: list[dict] = []
            skipped: list[dict] = []
            for match_key in matched_keys:
                control_item = control_groups[match_key]
                result_item = result_groups[match_key]
                control_source = control_item["path"]
                result_source = result_item["path"]
                if control_source.resolve() == result_source.resolve():
                    skipped.append({"name": result_item["raw_name"], "reason": "same source image"})
                    continue

                base_raw_name = result_item["raw_name"] or control_item["raw_name"]
                new_raw_name = self._unique_swapped_raw_name(
                    base_raw_name,
                    clean_suffix,
                    used_raw_names,
                    control_root,
                    result_root,
                    result_source.suffix,
                    control_source.suffix,
                )
                control_target = self._image_path_for_raw_name(control_root, new_raw_name, result_source.suffix)
                result_target = self._image_path_for_raw_name(result_root, new_raw_name, control_source.suffix)
                control_target.parent.mkdir(parents=True, exist_ok=True)
                result_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(result_source, control_target)
                shutil.copy2(control_source, result_target)
                used_raw_names.add(new_raw_name)
                created.append({
                    "name": new_raw_name,
                    "control_source": str(control_source),
                    "result_source": str(result_source),
                    "control_target": str(control_target),
                    "result_target": str(result_target),
                })

            summary = self.open_dirs(
                control1_dir=str(control_root),
                result_dir=str(result_root),
                control_count=max(1, self.control_count),
            )
            return {
                "swapped": len(created),
                "created": created,
                "skipped": skipped,
                "suffix": clean_suffix,
                "workspace": summary,
            }

    def _mark_global_segments_dirty(self):
        self._global_segments_dirty = True

    def _compute_workspace_key(self) -> str:
        payload = {
            "dirs": {key: str(value) if value else "" for key, value in self.dirs.items()},
            "control_count": self.control_count,
            "ignore_tokens": list(self.ignore_tokens),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def _workspace_state_path(self) -> Path:
        key = self.workspace_key or self._compute_workspace_key()
        return WORKSPACE_STATE_DIR / f"{key}.json"

    def _load_workspace_state(self):
        self.caption_overrides = {}
        self.caption_deleted = set()
        self.excluded_names = set()
        state_path = self._workspace_state_path()
        if not state_path.exists():
            return
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        captions = data.get("captions", {})
        if isinstance(captions, dict):
            self.caption_overrides = {
                str(name): str(content or "")
                for name, content in captions.items()
            }
        deleted = data.get("caption_deleted", data.get("deleted_captions", []))
        if isinstance(deleted, list):
            self.caption_deleted = {str(name) for name in deleted}
        excluded = data.get("excluded", [])
        if isinstance(excluded, list):
            self.excluded_names = {str(name) for name in excluded}

    def _save_workspace_state(self):
        if not self.workspace_key:
            self.workspace_key = self._compute_workspace_key()
        WORKSPACE_STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "workspace_key": self.workspace_key,
            "dirs": {key: str(value) if value else "" for key, value in self.dirs.items()},
            "captions": dict(sorted(self.caption_overrides.items())),
            "caption_deleted": sorted(self.caption_deleted, key=_natural_key),
            "excluded": sorted(self.excluded_names, key=_natural_key),
        }
        self._workspace_state_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _apply_workspace_state(self):
        valid_names = set(self.file_names)
        self.caption_overrides = {
            name: content
            for name, content in self.caption_overrides.items()
            if name in valid_names
        }
        self.caption_deleted = {name for name in self.caption_deleted if name in valid_names}
        self.caption_overrides = {
            name: content
            for name, content in self.caption_overrides.items()
            if name not in self.caption_deleted
        }
        self.excluded_names = {name for name in self.excluded_names if name in valid_names}
        for name, content in self.caption_overrides.items():
            self.txt_content[name] = content
        for name in self.caption_deleted:
            self.txt_content.pop(name, None)
        if self.excluded_names:
            self.file_names = [name for name in self.file_names if name not in self.excluded_names]

    def _has_caption(self, name: str) -> bool:
        if name in self.caption_deleted:
            return False
        if name in self.caption_overrides:
            return bool(str(self.caption_overrides.get(name, "") or "").strip())
        if name in self.txt_files:
            return bool(str(self.txt_content.get(name, "") or "").strip())
        return False

    def apply_name_aliases(self, aliases: dict[str, str]) -> dict:
        with self._lock:
            if not isinstance(aliases, dict) or not aliases:
                return self.get_workspace_summary()

            used_names: set[str] = set()
            rename_map: dict[str, str] = {}
            for name in self.file_names:
                alias = str(aliases.get(name, "") or "").strip().replace("\\", "/")
                next_name = alias or name
                next_name = self._ensure_unique_name(next_name, used_names)
                used_names.add(next_name)
                rename_map[name] = next_name

            if all(old == new for old, new in rename_map.items()):
                return self.get_workspace_summary()

            self.file_names = [rename_map[name] for name in self.file_names]
            for role in IMAGE_ROLES:
                self.files[role] = {
                    rename_map.get(name, name): path
                    for name, path in self.files[role].items()
                }
            self.txt_files = {
                rename_map.get(name, name): path
                for name, path in self.txt_files.items()
            }
            self.txt_content = {
                rename_map.get(name, name): content
                for name, content in self.txt_content.items()
            }
            self.caption_overrides = {
                rename_map.get(name, name): content
                for name, content in self.caption_overrides.items()
            }
            self.caption_deleted = {rename_map.get(name, name) for name in self.caption_deleted}
            self.excluded_names = {rename_map.get(name, name) for name in self.excluded_names}
            self._image_sizes.clear()
            self._resolution_mismatch.clear()
            self._resolution_index_ready = False
            self._mark_global_segments_dirty()
            self.file_names = sorted(self.file_names, key=_natural_key)
            return self.get_workspace_summary()

    def _normalize_match_part(self, value: str, *, strip_role_patterns: bool) -> str:
        value = (value or "").strip().lower()
        for token in self.ignore_tokens:
            if token:
                value = value.replace(token, " ")

        if strip_role_patterns:
            previous = None
            while previous != value:
                previous = value
                for pattern in ROLE_STRIP_PATTERNS:
                    value = re.sub(rf"^(?:{pattern})(?:[\s._-]+|$)", "", value)
                    value = re.sub(rf"(?:^|[\s._-]+)(?:{pattern})$", "", value)

        value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)
        return value

    def _normalize_match_key(self, stem: str) -> str:
        raw = (stem or "").strip().replace("\\", "/")
        parts = [part for part in raw.split("/") if part]
        if not parts:
            return raw.lower()

        normalized_parts: list[str] = []
        last_index = len(parts) - 1
        for index, part in enumerate(parts):
            normalized = self._normalize_match_part(part, strip_role_patterns=index == last_index)
            normalized_parts.append(normalized or part.strip().lower())
        return "/".join(normalized_parts)

    def _pick_display_name(self, group: dict, fallback: str) -> str:
        for role in ("result", "control1", "control2", "control3"):
            raw_name = group["raw_names"].get(role)
            if raw_name:
                return raw_name
        if group.get("txt_raw_name"):
            return str(group["txt_raw_name"])
        return fallback or "untitled"

    def _ensure_unique_name(self, name: str, used_names: set[str]) -> str:
        candidate = name or "untitled"
        if candidate not in used_names:
            return candidate
        index = 2
        while True:
            next_name = f"{candidate} [{index}]"
            if next_name not in used_names:
                return next_name
            index += 1

    def _relative_stem(self, root: Path, file: Path) -> str:
        try:
            relative = file.relative_to(root)
        except ValueError:
            relative = Path(file.name)
        return relative.with_suffix("").as_posix()

    def _scan_images(self, path: Optional[Path]) -> dict[str, Path]:
        if not path or not path.is_dir():
            return {}
        return {
            self._relative_stem(path, file): file
            for file in path.rglob("*")
            if file.is_file() and file.suffix.lower() in IMAGE_EXTS
        }

    def _group_images_by_match_key(self, images: dict[str, Path]) -> dict[str, dict]:
        groups: dict[str, dict] = {}
        for raw_name, path in images.items():
            match_key = self._normalize_match_key(raw_name)
            current = groups.get(match_key)
            if current is None or _natural_key(raw_name) < _natural_key(current["raw_name"]):
                groups[match_key] = {"raw_name": raw_name, "path": path}
        return groups

    def _image_path_for_raw_name(self, root: Path, raw_name: str, suffix: str) -> Path:
        parts = [part for part in str(raw_name or "").replace("\\", "/").split("/") if part]
        if not parts:
            parts = ["untitled"]
        return root.joinpath(*parts).with_suffix(suffix)

    def _clean_rename_basename(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("New file name is required.")
        if raw != Path(raw).name or any(char in INVALID_BASENAME_CHARS for char in raw):
            raise ValueError("New file name must not include a folder path.")
        suffix = Path(raw).suffix.lower()
        if suffix in IMAGE_EXTS or suffix == ".txt":
            raw = Path(raw).stem.strip()
        if not raw or raw in {".", ".."}:
            raise ValueError("New file name is invalid.")
        if raw.rstrip(" .") != raw:
            raise ValueError("New file name must not end with a space or dot.")
        if any(ord(char) < 32 for char in raw):
            raise ValueError("New file name contains invalid characters.")
        if raw.upper() in WINDOWS_RESERVED_NAMES:
            raise ValueError("New file name is reserved by Windows.")
        return raw

    def _clean_relative_folder(self, value: str) -> str:
        raw = str(value or "").strip().replace("\\", "/")
        if not raw:
            raise ValueError("Target folder is required.")
        if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
            raise ValueError("Target folder must be relative.")
        parts = [part.strip() for part in raw.split("/") if part.strip()]
        if not parts:
            raise ValueError("Target folder is required.")
        clean_parts: list[str] = []
        for part in parts:
            if part in {".", ".."} or any(char in INVALID_BASENAME_CHARS for char in part):
                raise ValueError("Target folder contains invalid characters.")
            if part.rstrip(" .") != part or any(ord(char) < 32 for char in part):
                raise ValueError("Target folder contains invalid characters.")
            if part.upper() in WINDOWS_RESERVED_NAMES:
                raise ValueError("Target folder contains a reserved name.")
            clean_parts.append(part)
        return "/".join(clean_parts)

    def _append_name_suffix(self, raw_name: str, suffix: str, index: int) -> str:
        raw_path = Path(str(raw_name or "untitled").replace("\\", "/"))
        extra = suffix if index <= 1 else f"{suffix}_{index}"
        next_name = f"{raw_path.name}{extra}"
        parent = raw_path.parent.as_posix()
        return next_name if parent in {"", "."} else f"{parent}/{next_name}"

    def _unique_swapped_raw_name(
        self,
        raw_name: str,
        suffix: str,
        used_raw_names: set[str],
        control_root: Path,
        result_root: Path,
        control_ext: str,
        result_ext: str,
    ) -> str:
        index = 1
        while True:
            candidate = self._append_name_suffix(raw_name, suffix, index)
            control_target = self._image_path_for_raw_name(control_root, candidate, control_ext)
            result_target = self._image_path_for_raw_name(result_root, candidate, result_ext)
            if candidate not in used_raw_names and not control_target.exists() and not result_target.exists():
                return candidate
            index += 1

    def _read_text_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return path.read_text(encoding="gbk", errors="replace")

    def _write_text_file(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")

    def _get_save_dir(self) -> Optional[Path]:
        return self.dirs["result"] or self.dirs["control1"]

    def _ensure_resolution_index(self):
        if self._resolution_index_ready:
            return
        for name in self.file_names:
            result_size = self._get_image_size("result", name)
            if not result_size:
                continue
            for role in CONTROL_ROLES[: self.control_count]:
                control_size = self._get_image_size(role, name)
                if control_size and control_size != result_size:
                    self._resolution_mismatch.add(name)
                    break
        self._resolution_index_ready = True

    def _get_image_size(self, role: str, name: str) -> Optional[tuple[int, int]]:
        cache_key = (role, name)
        if cache_key in self._image_sizes:
            return self._image_sizes[cache_key]

        path = self.files.get(role, {}).get(name)
        if not path or not path.exists():
            self._image_sizes[cache_key] = None
            return None

        try:
            with Image.open(path) as img:
                size = img.size
        except Exception:
            size = None
        self._image_sizes[cache_key] = size
        return size

    def get_workspace_summary(self) -> dict:
        with self._lock:
            self._ensure_resolution_index()
            visible_names = set(self.file_names)
            return {
                "workspace_key": self.workspace_key or self._compute_workspace_key(),
                "dirs": {key: str(value) if value else "" for key, value in self.dirs.items()},
                "settings": {
                    "control_count": self.control_count,
                    "ignore_tokens": list(self.ignore_tokens),
                },
                "counts": {
                    "control1": sum(1 for name in visible_names if name in self.files["control1"]),
                    "control2": sum(1 for name in visible_names if name in self.files["control2"]),
                    "control3": sum(1 for name in visible_names if name in self.files["control3"]),
                    "result": sum(1 for name in visible_names if name in self.files["result"]),
                    "txt": sum(1 for name in self.file_names if self._has_caption(name)),
                    "all": len(self.file_names),
                    "resolution_mismatch": len(self._resolution_mismatch),
                    "edited": sum(1 for name in self.file_names if name in self.caption_overrides),
                    "excluded": len(self.excluded_names),
                },
            }

    def list_items(
        self,
        *,
        filter_mode: str = "all",
        tag_query: str = "",
        detail: bool = False,
    ) -> dict:
        with self._lock:
            self._ensure_resolution_index()
            names = list(self.file_names)
            control1_files = self.files["control1"]
            control2_files = self.files["control2"]
            control3_files = self.files["control3"]
            result_files = self.files["result"]

            if filter_mode == "no_control1" and self.control_count >= 1:
                names = [name for name in names if name not in control1_files]
            elif filter_mode == "no_control2" and self.control_count >= 2:
                names = [name for name in names if name not in control2_files]
            elif filter_mode == "no_control3" and self.control_count >= 3:
                names = [name for name in names if name not in control3_files]
            elif filter_mode == "no_result":
                names = [name for name in names if name not in result_files]
            elif filter_mode == "no_txt":
                names = [name for name in names if not self._has_caption(name)]
            elif filter_mode == "res_mismatch":
                names = [name for name in names if name in self._resolution_mismatch]

            tag_query = (tag_query or "").strip().lower()
            if tag_query:
                names = [
                    name
                    for name in names
                    if tag_query in str(name).replace("\\", "/").lower()
                    or tag_query in self.txt_content.get(name, "").lower()
                    or any(tag_query in segment.lower() for segment in _parse_caption_segments(self.txt_content.get(name, "")))
                ]

            items = [
                self._serialize_item(name) if detail else self._serialize_item_summary(name, search_query=tag_query)
                for name in names
            ]
            global_segments = self.get_global_segments()
            return {
                "items": items,
                "stats": self._build_stats(filtered_count=len(items)),
                "global_segments": global_segments,
                "global_tags": global_segments,
            }

    def _item_search_matches(self, name: str, search_query: str) -> dict:
        query = (search_query or "").strip().lower()
        if not query:
            return {}
        text = self.txt_content.get(name, "")
        segments = [
            segment
            for segment in _parse_caption_segments(text)
            if query in segment.lower()
        ]
        return {
            "name": query in str(name).replace("\\", "/").lower(),
            "segments": segments,
        }

    def _serialize_item_summary(self, name: str, search_query: str = "") -> dict:
        control1_path = self.files["control1"].get(name)
        control2_path = self.files["control2"].get(name)
        control3_path = self.files["control3"].get(name)
        result_path = self.files["result"].get(name)
        item = {
            "name": name,
            "exists": {
                "control1": bool(control1_path),
                "control2": bool(control2_path),
                "control3": bool(control3_path),
                "result": bool(result_path),
                "txt": self._has_caption(name),
            },
            "flags": {
                "resolution_mismatch": name in self._resolution_mismatch,
            },
        }
        matches = self._item_search_matches(name, search_query)
        if matches:
            item["search_matches"] = matches
        return item

    def _build_stats(self, *, filtered_count: int) -> dict:
        control1_files = self.files["control1"]
        control2_files = self.files["control2"]
        control3_files = self.files["control3"]
        result_files = self.files["result"]
        return {
            "all": len(self.file_names),
            "filtered": filtered_count,
            "no_control1": sum(1 for name in self.file_names if name not in control1_files) if self.control_count >= 1 else 0,
            "no_control2": sum(1 for name in self.file_names if name not in control2_files) if self.control_count >= 2 else 0,
            "no_control3": sum(1 for name in self.file_names if name not in control3_files) if self.control_count >= 3 else 0,
            "no_result": sum(1 for name in self.file_names if name not in result_files),
            "no_txt": sum(1 for name in self.file_names if not self._has_caption(name)),
            "resolution_mismatch": len(self._resolution_mismatch),
            "edited": sum(1 for name in self.file_names if name in self.caption_overrides),
            "excluded": len(self.excluded_names),
        }

    def _serialize_item(self, name: str) -> dict:
        text = self.txt_content.get(name, "")
        segments = _parse_caption_segments(text)
        control1_path = self.files["control1"].get(name)
        control2_path = self.files["control2"].get(name)
        control3_path = self.files["control3"].get(name)
        result_path = self.files["result"].get(name)
        return {
            "name": name,
            "paths": {
                "control1": str(control1_path) if control1_path else "",
                "control2": str(control2_path) if control2_path else "",
                "control3": str(control3_path) if control3_path else "",
                "result": str(result_path) if result_path else "",
                "txt": str(self.txt_files.get(name, "")) if self._has_caption(name) and name in self.txt_files else "",
            },
            "exists": {
                "control1": bool(control1_path),
                "control2": bool(control2_path),
                "control3": bool(control3_path),
                "result": bool(result_path),
                "txt": self._has_caption(name),
            },
            "caption_source": "edited" if name in self.caption_overrides else "source" if self._has_caption(name) and name in self.txt_files else "",
            "tags": segments,
            "segments": segments,
            "text": text,
            "resolution": {
                "control1": self._get_image_size("control1", name),
                "control2": self._get_image_size("control2", name),
                "control3": self._get_image_size("control3", name),
                "result": self._get_image_size("result", name),
            },
            "flags": {
                "resolution_mismatch": name in self._resolution_mismatch,
            },
        }

    def get_item(self, name: str) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)
            self._ensure_resolution_index()
            return self._serialize_item(name)

    def get_global_segments(self) -> list[dict]:
        with self._lock:
            if not self._global_segments_dirty:
                return [dict(row) for row in self._global_segments_cache]
            counter = Counter()
            for name in self.file_names:
                content = self.txt_content.get(name, "")
                counter.update(_parse_caption_segments(content))
            self._global_segments_cache = [
                {"segment": segment, "tag": segment, "count": count}
                for segment, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
            ]
            self._global_segments_dirty = False
            return [dict(row) for row in self._global_segments_cache]

    def get_global_tags(self) -> list[dict]:
        return self.get_global_segments()

    def save_segments(self, name: str, segments: list[str]) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)

            content = ", ".join(_normalize_segment_inputs(segments))
            return self.save_text(name, content)

    def save_tags(self, name: str, tags: list[str]) -> dict:
        return self.save_segments(name, tags)

    def save_text(self, name: str, content: str) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)

            content = str(content or "")
            if content.strip():
                self.txt_content[name] = content
                self.caption_overrides[name] = content
                self.caption_deleted.discard(name)
            else:
                self.txt_content.pop(name, None)
                self.caption_overrides.pop(name, None)
                self.caption_deleted.add(name)
            self.excluded_names.discard(name)
            self._save_workspace_state()
            self._mark_global_segments_dirty()
            return self._serialize_item(name)

    def batch_add_segments(self, names: list[str], segments: list[str], position: str = "after") -> dict:
        additions = _normalize_segment_inputs(segments)
        if not additions:
            return {"changed": 0}
        insert_position = "before" if position == "before" else "after"
        changed = 0
        for name in names:
            original = self.txt_content.get(name, "")
            updated = _merge_text_with_segments(original, additions, insert_position)
            if updated != original:
                self.save_text(name, updated)
                changed += 1
        return {"changed": changed}

    def batch_add_tags(self, names: list[str], tags: list[str], position: str = "after") -> dict:
        return self.batch_add_segments(names, tags, position)

    def batch_delete_segments(self, names: list[str], segments: list[str]) -> dict:
        needles = [segment.lower() for segment in _normalize_segment_inputs(segments)]
        if not needles:
            return {"changed": 0}
        changed = 0
        for name in names:
            original = self.txt_content.get(name, "")
            updated = _delete_caption_segments(original, needles)
            if updated != original:
                self.save_text(name, updated)
                changed += 1
        return {"changed": changed}

    def batch_delete_tags(self, names: list[str], tags: list[str]) -> dict:
        return self.batch_delete_segments(names, tags)

    def batch_replace_segment(self, names: list[str], old_segment: str, new_segment: str) -> dict:
        changed = 0
        old_segment = (old_segment or "").strip().lower()
        new_segment = (new_segment or "").strip()
        if not old_segment:
            return {"changed": 0}
        for name in names:
            original = self.txt_content.get(name, "")
            updated = _replace_caption_segment(original, old_segment, new_segment)
            if updated != original:
                self.save_text(name, updated)
                changed += 1
        return {"changed": changed}

    def batch_replace_tag(self, names: list[str], old_tag: str, new_tag: str) -> dict:
        return self.batch_replace_segment(names, old_tag, new_tag)

    def _batch_rename_basename(
        self,
        basename: str,
        *,
        operation: str,
        value: str = "",
        old_value: str = "",
        new_value: str = "",
    ) -> str:
        operation = (operation or "").strip().lower()
        if operation == "add_prefix":
            addition = str(value or "")
            if not addition:
                raise ValueError("Rename text is required.")
            return self._clean_rename_basename(f"{addition}{basename}")
        if operation == "add_suffix":
            addition = str(value or "")
            if not addition:
                raise ValueError("Rename text is required.")
            return self._clean_rename_basename(f"{basename}{addition}")
        if operation == "delete":
            tokens = _parse_rename_tokens(value)
            if not tokens:
                raise ValueError("Delete text is required.")
            updated = basename
            for token in tokens:
                updated = updated.replace(token, "")
            return self._clean_rename_basename(updated)
        if operation == "replace":
            old_text = str(old_value or "")
            if not old_text:
                raise ValueError("Old rename text is required.")
            return self._clean_rename_basename(basename.replace(old_text, str(new_value or "")))
        raise ValueError(f"Unsupported batch rename operation: {operation}")

    def batch_rename_items(
        self,
        names: list[str],
        *,
        operation: str,
        value: str = "",
        old_value: str = "",
        new_value: str = "",
    ) -> dict:
        with self._lock:
            selected_names = [str(name or "") for name in names if str(name or "") in self.file_names]
            if not selected_names:
                return {"changed": 0, "renamed": [], "workspace": self.get_workspace_summary()}

            selected_set = set(selected_names)
            rename_map: dict[str, str] = {}
            for name in selected_names:
                old_name_path = Path(str(name).replace("\\", "/"))
                parent = old_name_path.parent.as_posix()
                basename = old_name_path.name
                clean_basename = self._batch_rename_basename(
                    basename,
                    operation=operation,
                    value=value,
                    old_value=old_value,
                    new_value=new_value,
                )
                new_name = clean_basename if parent in {"", "."} else f"{parent}/{clean_basename}"
                rename_map[name] = new_name

            changed_map = {old: new for old, new in rename_map.items() if old != new}
            if not changed_map:
                return {"changed": 0, "renamed": [], "workspace": self.get_workspace_summary()}

            target_names = list(rename_map.values())
            duplicate_targets = [name for name, count in Counter(target_names).items() if count > 1]
            if duplicate_targets:
                raise FileExistsError(f"Batch rename would create duplicate item names: {', '.join(sorted(duplicate_targets, key=_natural_key))}")
            existing_conflicts = [name for name in target_names if name in self.file_names and name not in selected_set]
            if existing_conflicts:
                raise FileExistsError(f"Item already exists: {existing_conflicts[0]}")

            file_pairs: list[tuple[Path, Path]] = []
            for old_name, new_name in changed_map.items():
                clean_basename = Path(new_name.replace("\\", "/")).name
                for role in IMAGE_ROLES:
                    source = self.files[role].get(old_name)
                    if source:
                        target = source.with_name(f"{clean_basename}{source.suffix}")
                        if target != source:
                            file_pairs.append((source, target))
                txt_source = self.txt_files.get(old_name)
                if txt_source:
                    target = txt_source.with_name(f"{clean_basename}{txt_source.suffix}")
                    if target != txt_source:
                        file_pairs.append((txt_source, target))

            sources = {source.resolve() for source, _ in file_pairs}
            targets: set[Path] = set()
            for source, target in file_pairs:
                resolved_target = target.resolve()
                if resolved_target in targets:
                    raise FileExistsError(f"Batch rename would create duplicate file: {target}")
                targets.add(resolved_target)
                if target.exists() and resolved_target not in sources:
                    raise FileExistsError(f"Target file already exists: {target}")

            staged: list[tuple[Path, Path]] = []
            finalized: list[tuple[Path, Path]] = []
            try:
                for index, (source, _) in enumerate(file_pairs):
                    if not source.exists():
                        raise FileNotFoundError(f"Source file does not exist: {source}")
                    temp = source.with_name(f".vds_batch_rename_{uuid.uuid4().hex}_{index}{source.suffix}")
                    while temp.exists():
                        temp = source.with_name(f".vds_batch_rename_{uuid.uuid4().hex}_{index}{source.suffix}")
                    source.rename(temp)
                    staged.append((source, temp))

                for (source, target), (_, temp) in zip(file_pairs, staged):
                    temp.rename(target)
                    finalized.append((source, target))
            except Exception:
                for source, target in reversed(finalized):
                    try:
                        if target.exists() and not source.exists():
                            target.rename(source)
                    except Exception:
                        pass
                for source, temp in reversed(staged):
                    try:
                        if temp.exists() and not source.exists():
                            temp.rename(source)
                    except Exception:
                        pass
                raise

            moved_paths = {source: target for source, target in file_pairs}
            self.file_names = [rename_map.get(name, name) for name in self.file_names]
            for role in IMAGE_ROLES:
                self.files[role] = {
                    rename_map.get(name, name): moved_paths.get(path, path)
                    for name, path in self.files[role].items()
                }
            self.txt_files = {
                rename_map.get(name, name): moved_paths.get(path, path)
                for name, path in self.txt_files.items()
            }
            self.txt_content = {
                rename_map.get(name, name): content
                for name, content in self.txt_content.items()
            }
            self.caption_overrides = {
                rename_map.get(name, name): content
                for name, content in self.caption_overrides.items()
            }
            self.caption_deleted = {rename_map.get(name, name) for name in self.caption_deleted}
            self.excluded_names = {rename_map.get(name, name) for name in self.excluded_names}
            self._image_sizes.clear()
            self._resolution_mismatch.clear()
            self._resolution_index_ready = False
            self._mark_global_segments_dirty()
            self.file_names = sorted(self.file_names, key=_natural_key)
            self._save_workspace_state()
            self._ensure_resolution_index()
            return {
                "changed": len(changed_map),
                "renamed": [{"old_name": old, "new_name": new} for old, new in changed_map.items()],
                "workspace": self.get_workspace_summary(),
            }

    def rename_item(self, name: str, new_basename: str) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)

            clean_basename = self._clean_rename_basename(new_basename)
            old_name_path = Path(str(name).replace("\\", "/"))
            parent = old_name_path.parent.as_posix()
            new_name = clean_basename if parent in {"", "."} else f"{parent}/{clean_basename}"
            if new_name != name and new_name in self.file_names:
                raise FileExistsError(f"Item already exists: {new_name}")

            rename_pairs: list[tuple[Path, Path]] = []
            for role in IMAGE_ROLES:
                source = self.files[role].get(name)
                if not source:
                    continue
                target = source.with_name(f"{clean_basename}{source.suffix}")
                if target != source:
                    if target.exists():
                        raise FileExistsError(f"Target file already exists: {target}")
                    rename_pairs.append((source, target))

            txt_source = self.txt_files.get(name)
            if txt_source:
                txt_target = txt_source.with_name(f"{clean_basename}{txt_source.suffix}")
                if txt_target != txt_source:
                    if txt_target.exists():
                        raise FileExistsError(f"Target file already exists: {txt_target}")
                    rename_pairs.append((txt_source, txt_target))

            renamed: list[tuple[Path, Path]] = []
            try:
                for source, target in rename_pairs:
                    if not source.exists():
                        raise FileNotFoundError(f"Source file does not exist: {source}")
                    source.rename(target)
                    renamed.append((source, target))
            except Exception:
                for source, target in reversed(renamed):
                    try:
                        if target.exists() and not source.exists():
                            target.rename(source)
                    except Exception:
                        pass
                raise

            moved_paths = {source: target for source, target in rename_pairs}
            self.file_names = [new_name if item == name else item for item in self.file_names]
            for role in IMAGE_ROLES:
                if name in self.files[role]:
                    source = self.files[role].pop(name)
                    self.files[role][new_name] = moved_paths.get(source, source)
            if name in self.txt_files:
                source = self.txt_files.pop(name)
                self.txt_files[new_name] = moved_paths.get(source, source)
            if name in self.txt_content:
                self.txt_content[new_name] = self.txt_content.pop(name)
            if name in self.caption_overrides:
                self.caption_overrides[new_name] = self.caption_overrides.pop(name)
            if name in self.caption_deleted:
                self.caption_deleted.discard(name)
                self.caption_deleted.add(new_name)
            if name in self.excluded_names:
                self.excluded_names.discard(name)
                self.excluded_names.add(new_name)

            self._image_sizes.clear()
            self._resolution_mismatch.clear()
            self._resolution_index_ready = False
            self._mark_global_segments_dirty()
            self.file_names = sorted(self.file_names, key=_natural_key)
            self._save_workspace_state()
            self._ensure_resolution_index()
            return {
                "old_name": name,
                "new_name": new_name,
                "renamed": [{"from": str(source), "to": str(target)} for source, target in rename_pairs],
                "item": self._serialize_item(new_name),
                "workspace": self.get_workspace_summary(),
            }

    def move_item_to_folder(self, name: str, target_folder: str) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)

            clean_folder = self._clean_relative_folder(target_folder)
            old_name_path = Path(str(name).replace("\\", "/"))
            basename = old_name_path.name
            current_folder = old_name_path.parent.as_posix()
            current_folder = "" if current_folder == "." else current_folder
            new_name = f"{clean_folder}/{basename}"
            if clean_folder == current_folder:
                return {
                    "old_name": name,
                    "new_name": name,
                    "moved": [],
                    "item": self._serialize_item(name),
                    "workspace": self.get_workspace_summary(),
                }
            if new_name in self.file_names:
                raise FileExistsError(f"Item already exists: {new_name}")

            move_pairs: list[tuple[Path, Path]] = []
            folder_parts = clean_folder.split("/")
            for role in IMAGE_ROLES:
                source = self.files[role].get(name)
                root = self.dirs.get(role)
                if not source or not root:
                    continue
                target = root.joinpath(*folder_parts, source.name)
                if target == source:
                    continue
                if target.exists():
                    raise FileExistsError(f"Target file already exists: {target}")
                move_pairs.append((source, target))

            txt_source = self.txt_files.get(name)
            txt_root = self.dirs.get("result")
            if txt_source and txt_root:
                txt_target = txt_root.joinpath(*folder_parts, txt_source.name)
                if txt_target != txt_source:
                    if txt_target.exists():
                        raise FileExistsError(f"Target file already exists: {txt_target}")
                    move_pairs.append((txt_source, txt_target))

            moved: list[tuple[Path, Path]] = []
            try:
                for source, target in move_pairs:
                    if not source.exists():
                        raise FileNotFoundError(f"Source file does not exist: {source}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source.rename(target)
                    moved.append((source, target))
            except Exception:
                for source, target in reversed(moved):
                    try:
                        if target.exists() and not source.exists():
                            source.parent.mkdir(parents=True, exist_ok=True)
                            target.rename(source)
                    except Exception:
                        pass
                raise

            moved_paths = {source: target for source, target in move_pairs}
            self.file_names = [new_name if item == name else item for item in self.file_names]
            for role in IMAGE_ROLES:
                if name in self.files[role]:
                    source = self.files[role].pop(name)
                    self.files[role][new_name] = moved_paths.get(source, source)
            if name in self.txt_files:
                source = self.txt_files.pop(name)
                self.txt_files[new_name] = moved_paths.get(source, source)
            if name in self.txt_content:
                self.txt_content[new_name] = self.txt_content.pop(name)
            if name in self.caption_overrides:
                self.caption_overrides[new_name] = self.caption_overrides.pop(name)
            if name in self.caption_deleted:
                self.caption_deleted.discard(name)
                self.caption_deleted.add(new_name)
            if name in self.excluded_names:
                self.excluded_names.discard(name)
                self.excluded_names.add(new_name)

            self._image_sizes.clear()
            self._resolution_mismatch.clear()
            self._resolution_index_ready = False
            self._mark_global_segments_dirty()
            self.file_names = sorted(self.file_names, key=_natural_key)
            self._save_workspace_state()
            self._ensure_resolution_index()
            return {
                "old_name": name,
                "new_name": new_name,
                "moved": [{"from": str(source), "to": str(target)} for source, target in move_pairs],
                "item": self._serialize_item(new_name),
                "workspace": self.get_workspace_summary(),
            }

    def delete_item(self, name: str) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)

            self.excluded_names.add(name)
            self.caption_overrides.pop(name, None)
            self.caption_deleted.discard(name)
            self._mark_global_segments_dirty()
            self.file_names = [item for item in self.file_names if item != name]
            self._resolution_mismatch.discard(name)
            for key in list(self._image_sizes.keys()):
                if key[1] == name:
                    self._image_sizes.pop(key, None)
            self._save_workspace_state()

            return {
                "removed": [],
                "errors": [],
                "excluded": [name],
                "message": "Item excluded from export set. Source files were not changed.",
            }

    def primary_item_path(self, name: str) -> Path:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)
            for role in ("result", "control1", "control2", "control3"):
                path = self.files.get(role, {}).get(name)
                if path and path.exists():
                    return path
            txt_path = self.txt_files.get(name)
            if txt_path and txt_path.exists():
                return txt_path
            raise FileNotFoundError(f"No source file found for item: {name}")

    def trash_item_files(self, name: str) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)

            path_entries: list[tuple[str, Path]] = []
            seen_paths: set[Path] = set()
            for role in IMAGE_ROLES:
                path = self.files[role].get(name)
                if path and path.exists() and path not in seen_paths:
                    path_entries.append((role, path))
                    seen_paths.add(path)
            txt_path = self.txt_files.get(name)
            if txt_path and txt_path.exists() and txt_path not in seen_paths:
                path_entries.append(("txt", txt_path))
                seen_paths.add(txt_path)

            if not path_entries:
                self.file_names = [item for item in self.file_names if item != name]
                self.caption_overrides.pop(name, None)
                self.caption_deleted.discard(name)
                self.excluded_names.discard(name)
                self._save_workspace_state()
                return {"trashed": [], "workspace": self.get_workspace_summary()}

            trashed: list[tuple[str, Path]] = []
            for role, path in path_entries:
                _send_to_trash(path)
                trashed.append((role, path))

            for role, path in trashed:
                if role in IMAGE_ROLES and self.files[role].get(name) == path:
                    self.files[role].pop(name, None)
                elif role == "txt" and self.txt_files.get(name) == path:
                    self.txt_files.pop(name, None)
                    self.txt_content.pop(name, None)

            self.caption_overrides.pop(name, None)
            self.caption_deleted.discard(name)
            self.excluded_names.discard(name)
            has_remaining = any(name in self.files[role] for role in IMAGE_ROLES) or name in self.txt_files
            if not has_remaining:
                self.file_names = [item for item in self.file_names if item != name]
            for key in list(self._image_sizes.keys()):
                if key[1] == name:
                    self._image_sizes.pop(key, None)
            self._resolution_mismatch.discard(name)
            self._resolution_index_ready = False
            self._mark_global_segments_dirty()
            self._save_workspace_state()
            self._ensure_resolution_index()
            return {
                "trashed": [{"role": role, "path": str(path)} for role, path in trashed],
                "removed_name": name if not has_remaining else "",
                "workspace": self.get_workspace_summary(),
            }

    def get_export_items(self, names: Optional[list[str]] = None) -> list[dict]:
        with self._lock:
            self._ensure_resolution_index()
            export_names = list(names) if names else list(self.file_names)
            return [
                self._serialize_item(name)
                for name in export_names
                if name in self.file_names and name not in self.excluded_names
            ]

    def resolve_image_path(self, role: str, name: str) -> Optional[Path]:
        with self._lock:
            return self.files.get(role, {}).get(name)

    def replace_item_paths(self, name: str, paths: dict[str, str]) -> dict:
        with self._lock:
            if name not in self.file_names:
                raise KeyError(name)
            for role, value in (paths or {}).items():
                if role not in IMAGE_ROLES:
                    continue
                path = Path(str(value or ""))
                if not path.is_file():
                    continue
                self.files[role][name] = path
            for key in list(self._image_sizes.keys()):
                if key[1] == name:
                    self._image_sizes.pop(key, None)
            self._resolution_mismatch.discard(name)
            self._resolution_index_ready = False
            self._ensure_resolution_index()
            return self._serialize_item(name)

    def translate_text(self, text: str) -> str:
        query = (text or "").strip()
        if not query:
            return ""
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx&sl=auto&tl=zh-CN&dt=t&q="
            + urllib.parse.quote(query)
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return "".join(item[0] for item in data[0] if item[0])
