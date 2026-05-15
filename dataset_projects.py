from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from dataset_paths import PROJECTS_DIR, ensure_dataset_dirs, is_relative_to
from dataset_workspace import CONTROL_ROLES, IMAGE_ROLES


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _clean_name(value: str, fallback: str = "未命名项目") -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", value or fallback).strip()
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or fallback


def _project_id(name: str) -> str:
    return f"{_now_id()}_{_clean_name(name)}"


def _safe_project_dir(project_id: str) -> Path:
    raw = (project_id or "").strip()
    if not raw:
        raise ValueError("Missing project id.")
    path = (PROJECTS_DIR / raw).resolve()
    if not is_relative_to(path, PROJECTS_DIR):
        raise ValueError("Invalid project id.")
    return path


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    base = path.parent / path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = Path(f"{base}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _item_target_stem(name: str, used: set[str]) -> str:
    base = _clean_name(Path(name).stem, "item")
    candidate = base
    index = 2
    while candidate.lower() in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate.lower())
    return candidate


def _copy_item_assets(project_dir: Path, items: list[dict], control_count: int) -> tuple[dict, list[dict]]:
    role_dirs = {role: project_dir / role for role in IMAGE_ROLES}
    for role_dir in role_dirs.values():
        role_dir.mkdir(parents=True, exist_ok=True)
    captions_dir = project_dir / "captions"
    captions_dir.mkdir(parents=True, exist_ok=True)

    used_stems: set[str] = set()
    item_rows: list[dict] = []
    cover = ""
    active_roles = list(CONTROL_ROLES[: max(1, min(3, int(control_count or 1)))]) + ["result"]

    for item in items:
        stem = _item_target_stem(str(item.get("name", "item")), used_stems)
        paths = item.get("paths", {}) if isinstance(item.get("paths"), dict) else {}
        row = {"name": stem, "source_name": item.get("name", ""), "roles": {}, "caption": item.get("text", "") or ""}
        for role in active_roles:
            source_value = paths.get(role, "")
            if not source_value:
                continue
            source = Path(source_value)
            if not source.is_file():
                continue
            target = _unique_path(role_dirs[role] / f"{stem}{source.suffix.lower()}")
            shutil.copy2(source, target)
            row["roles"][role] = str(target.relative_to(project_dir))
            if not cover and role == "result":
                cover = str(target.relative_to(project_dir))
            elif not cover:
                cover = str(target.relative_to(project_dir))

        caption = str(item.get("text", "") or "")
        if caption:
            (captions_dir / f"{stem}.txt").write_text(caption, encoding="utf-8")
            (role_dirs["result"] / f"{stem}.txt").write_text(caption, encoding="utf-8")
        item_rows.append(row)

    dirs = {role: str(role_dirs[role]) for role in active_roles if role_dirs[role].exists()}
    return {"dirs": dirs, "cover": cover}, item_rows


class ProjectStore:
    def __init__(self, projects_dir: Path = PROJECTS_DIR):
        self.projects_dir = projects_dir

    def ensure(self) -> None:
        ensure_dataset_dirs()
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[dict]:
        self.ensure()
        rows: list[dict] = []
        for path in self.projects_dir.iterdir():
            if not path.is_dir():
                continue
            meta = _read_json(path / "project.json")
            stat = path.stat()
            rows.append(
                {
                    "id": path.name,
                    "name": meta.get("name") or path.name,
                    "created_at": meta.get("created_at", ""),
                    "updated_at": meta.get("updated_at", datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")),
                    "item_count": int(meta.get("item_count", 0) or 0),
                    "captioned_count": int(meta.get("captioned_count", 0) or 0),
                    "control_count": int(meta.get("control_count", 1) or 1),
                    "thumbnail": meta.get("thumbnail", ""),
                    "path": str(path),
                }
            )
        return sorted(rows, key=lambda row: row.get("updated_at", ""), reverse=True)

    def get_project(self, project_id: str) -> dict:
        path = _safe_project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        meta = _read_json(path / "project.json")
        workspace = _read_json(path / "workspace.json")
        return {"project": meta, "workspace": workspace, "path": str(path)}

    def save_project(self, *, name: str, workspace, overwrite_id: str = "") -> dict:
        self.ensure()
        items = workspace.get_export_items()
        if not items:
            raise ValueError("当前工作区没有可保存的条目。")

        if overwrite_id:
            project_dir = _safe_project_dir(overwrite_id)
            if project_dir.exists():
                shutil.rmtree(project_dir)
            project_id = project_dir.name
        else:
            project_id = _project_id(name)
            project_dir = _safe_project_dir(project_id)
            index = 2
            while project_dir.exists():
                project_id = f"{_project_id(name)}_{index}"
                project_dir = _safe_project_dir(project_id)
                index += 1

        project_dir.mkdir(parents=True, exist_ok=True)
        summary = workspace.get_workspace_summary()
        copied, item_rows = _copy_item_assets(project_dir, items, summary["settings"]["control_count"])
        now = datetime.now().isoformat(timespec="seconds")
        captioned = sum(1 for item in items if item.get("text"))
        project_name = _clean_name(name or project_id)
        meta = {
            "id": project_id,
            "name": project_name,
            "created_at": now,
            "updated_at": now,
            "item_count": len(items),
            "captioned_count": captioned,
            "control_count": summary["settings"]["control_count"],
            "thumbnail": copied["cover"],
            "dirs": copied["dirs"],
        }
        workspace_state = {
            "project_id": project_id,
            "project_name": project_name,
            "settings": summary.get("settings", {}),
            "dirs": copied["dirs"],
            "items": item_rows,
        }
        _write_json(project_dir / "project.json", meta)
        _write_json(project_dir / "workspace.json", workspace_state)
        return {"project": meta, "workspace": workspace_state}

    def rename_project(self, project_id: str, name: str) -> dict:
        path = _safe_project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        meta = _read_json(path / "project.json")
        meta["name"] = _clean_name(name)
        meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _write_json(path / "project.json", meta)
        return meta

    def delete_project(self, project_id: str) -> dict:
        path = _safe_project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        shutil.rmtree(path)
        return {"deleted": project_id}
