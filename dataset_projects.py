from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from dataset_paths import is_relative_to
from dataset_workspace import CONTROL_ROLES, IMAGE_EXTS


APP_DATA_DIR = Path.home() / ".vision_dataset_studio"
LEGACY_APP_DATA_DIR = Path.home() / ".lora_dataset_edit"
PROJECTS_DIR = APP_DATA_DIR / "projects"
TRASH_DIR = APP_DATA_DIR / "trash"
PROJECT_INDEX_FILE = APP_DATA_DIR / "projects_index.json"
LEGACY_PROJECTS_DIR = LEGACY_APP_DATA_DIR / "projects"
SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _clean_name(value: str, fallback: str = "未命名项目") -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", value or fallback).strip()
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or fallback


def _slug(value: str, fallback: str = "project") -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", _clean_name(value, fallback), flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-._ ")
    return slug or fallback


def _project_id(name: str) -> str:
    return f"{_now_id()}-{_slug(name, 'project')}"


def _renamed_project_id(old_id: str, name: str) -> str:
    prefix_match = re.match(r"^(\d{8}-\d{6})[-_]", old_id or "")
    prefix = prefix_match.group(1) if prefix_match else _now_id()
    return f"{prefix}-{_slug(name, 'project')}"


def _safe_project_dir(project_id: str, *, root: Path = PROJECTS_DIR) -> Path:
    raw = (project_id or "").strip()
    if not raw:
        raise ValueError("Missing project id.")
    path = (root / raw).resolve()
    if not is_relative_to(path, root):
        raise ValueError("Invalid project id.")
    return path


def _read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if fallback is None else fallback


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _item_target_stem(name: str, used: set[str]) -> str:
    raw = str(name or "item").replace("\\", "/")
    parts = [part for part in raw.split("/") if part]
    if not parts:
        parts = ["item"]
    parts[-1] = Path(parts[-1]).stem
    clean_parts = [_clean_name(part, "item") for part in parts]
    base = "/".join(clean_parts) or "item"
    candidate = base
    index = 2
    while candidate.lower() in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate.lower())
    return candidate


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _project_paths(project_dir: Path) -> dict[str, Path]:
    return {
        "project": project_dir / "project.json",
        "manifest": project_dir / "manifest.json",
        "workspace": project_dir / "workspace.json",
        "assets": project_dir / "assets",
        "captions": project_dir / "captions",
        "state": project_dir / "state",
        "thumbnails": project_dir / "thumbnails",
    }


def _captioned_count(items: list[dict]) -> int:
    return sum(1 for item in items if str(item.get("caption", "") or "").strip())


def _active_roles(control_count: int) -> list[str]:
    count = 1 if control_count is None else int(control_count)
    return list(CONTROL_ROLES[: max(0, min(3, count))]) + ["result"]


def _workspace_dirs(project_dir: Path, control_count: int) -> dict[str, str]:
    assets_dir = project_dir / "assets"
    return {
        role: str((assets_dir / role).resolve())
        for role in _active_roles(control_count)
        if (assets_dir / role).exists()
    }


def _old_asset_maps(project_dir: Path) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    manifest = _read_json(project_dir / "manifest.json", {})
    by_name: dict[tuple[str, str], str] = {}
    by_source: dict[tuple[str, str], str] = {}
    for item in manifest.get("items", []) if isinstance(manifest.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "") or item.get("name", "") or "")
        source_name = str(item.get("source_name", "") or "")
        assets = item.get("assets", {}) if isinstance(item.get("assets"), dict) else {}
        for role, rel in assets.items():
            if item_id and rel:
                by_name[(item_id, role)] = str(rel)
            if source_name and rel:
                by_source[(source_name, role)] = str(rel)
    workspace = _read_json(project_dir / "workspace.json", {})
    for item in workspace.get("items", []) if isinstance(workspace.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("name", "") or "")
        source_name = str(item.get("source_name", "") or "")
        roles = item.get("roles", {}) if isinstance(item.get("roles"), dict) else {}
        for role, rel in roles.items():
            normalized = str(rel).replace("\\", "/")
            if item_id and normalized:
                by_name.setdefault((item_id, role), normalized)
            if source_name and normalized:
                by_source.setdefault((source_name, role), normalized)
    return by_name, by_source


def _cleanup_project_assets(project_dir: Path, active_roles: list[str], keep_files: set[Path]) -> None:
    assets_dir = project_dir / "assets"
    active = set(active_roles)
    if not assets_dir.is_dir():
        return

    for role_dir in assets_dir.iterdir():
        if not role_dir.is_dir():
            continue
        if role_dir.name not in active:
            shutil.rmtree(role_dir, ignore_errors=True)
            continue
        for path in sorted(role_dir.rglob("*"), reverse=True):
            if path.is_file() and path.resolve() not in keep_files and path.suffix.lower() in IMAGE_EXTS | {".txt"}:
                path.unlink(missing_ok=True)
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass


def _sync_directory_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    wanted: set[Path] = {target.resolve()}

    for source_path in sorted(source.rglob("*")):
        relative = source_path.relative_to(source)
        target_path = target / relative
        wanted.add(target_path.resolve())
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    if not target.exists():
        return
    for target_path in sorted(target.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        resolved = target_path.resolve()
        if resolved in wanted:
            continue
        if target_path.is_file() or target_path.is_symlink():
            target_path.unlink(missing_ok=True)
        elif target_path.is_dir():
            try:
                target_path.rmdir()
            except OSError:
                pass


class ProjectStore:
    def __init__(self, projects_dir: Path = PROJECTS_DIR, legacy_projects_dir: Path | None = None):
        self.projects_dir = projects_dir
        self.app_dir = self.projects_dir.parent
        self.trash_dir = self.app_dir / "trash"
        self.index_file = self.app_dir / "projects_index.json"
        if legacy_projects_dir is not None:
            self.legacy_projects_dir: Path | None = legacy_projects_dir
            self.legacy_app_dir: Path | None = legacy_projects_dir.parent
        elif self.projects_dir == PROJECTS_DIR:
            self.legacy_projects_dir = LEGACY_PROJECTS_DIR
            self.legacy_app_dir = LEGACY_APP_DATA_DIR
        else:
            self.legacy_projects_dir = None
            self.legacy_app_dir = None

    def _migrate_legacy_app_dir(self) -> None:
        legacy_app_dir = self.legacy_app_dir
        if not legacy_app_dir or legacy_app_dir == self.app_dir or not legacy_app_dir.exists():
            return
        if not self.app_dir.exists():
            self.app_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                legacy_app_dir.replace(self.app_dir)
                return
            except OSError:
                pass
        shutil.copytree(legacy_app_dir, self.app_dir, dirs_exist_ok=True)

    def ensure(self) -> None:
        self._migrate_legacy_app_dir()
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        return _safe_project_dir(project_id, root=self.projects_dir)

    def _write_index(self, rows: list[dict]) -> None:
        _write_json(self.index_file, {"schema_version": SCHEMA_VERSION, "projects": rows})

    def _cleanup_tmp_projects(self, project_id: str) -> None:
        prefix = f".tmp-{project_id}-"
        if not self.projects_dir.is_dir():
            return
        for path in self.projects_dir.iterdir():
            if not path.is_dir() or not path.name.startswith(prefix):
                continue
            shutil.rmtree(path, ignore_errors=True)

    def _refresh_index(self) -> list[dict]:
        rows = self.list_projects(write_index=False)
        self._write_index(rows)
        return rows

    def list_projects(self, *, write_index: bool = True) -> list[dict]:
        self.ensure()
        rows: list[dict] = []
        for path in self.projects_dir.iterdir():
            if not path.is_dir() or path.name.startswith("."):
                continue
            meta = _read_json(path / "project.json", {})
            if not meta:
                continue
            stat = path.stat()
            rows.append(
                {
                    "id": meta.get("id") or path.name,
                    "name": meta.get("name") or path.name,
                    "created_at": meta.get("created_at", ""),
                    "updated_at": meta.get("updated_at", datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")),
                    "item_count": int(meta.get("item_count", 0) or 0),
                    "captioned_count": int(meta.get("captioned_count", 0) or 0),
                    "control_count": int(meta.get("control_count", 1)),
                    "thumbnail": meta.get("thumbnail", ""),
                    "path": str(path),
                }
            )
        rows = sorted(rows, key=lambda row: row.get("updated_at", ""), reverse=True)
        if write_index:
            self._write_index(rows)
        return rows

    def get_project(self, project_id: str) -> dict:
        path = self._project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        meta = _read_json(path / "project.json", {})
        workspace = _read_json(path / "workspace.json", {})
        manifest = _read_json(path / "manifest.json", {"items": []})
        return {"project": meta, "workspace": workspace, "manifest": manifest, "path": str(path)}

    def _unique_project_dir(self, name: str) -> tuple[str, Path]:
        project_id = _project_id(name)
        project_dir = self._project_dir(project_id)
        index = 2
        while project_dir.exists():
            project_id = f"{_project_id(name)}-{index}"
            project_dir = self._project_dir(project_id)
            index += 1
        return project_id, project_dir

    def save_project(
        self,
        *,
        name: str,
        workspace,
        overwrite_id: str = "",
        control_count: int | None = None,
        ui_state: dict | None = None,
    ) -> dict:
        self.ensure()
        items = workspace.get_export_items()
        if not items:
            raise ValueError("当前工作区没有可保存的条目。")

        staging_dir: Path | None = None
        if overwrite_id:
            project_id = overwrite_id
            final_project_dir = self._project_dir(project_id)
            if not final_project_dir.is_dir():
                raise FileNotFoundError(f"Project not found: {project_id}")
            existing_meta = _read_json(final_project_dir / "project.json", {})
            staging_dir = self._project_dir(f".tmp-{project_id}-{_now_id()}")
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            shutil.copytree(final_project_dir, staging_dir)
            project_dir = staging_dir
        else:
            project_id, final_project_dir = self._unique_project_dir(name)
            project_dir = final_project_dir
            existing_meta = {}

        paths = _project_paths(project_dir)
        public_paths = _project_paths(final_project_dir)
        for key in ("assets", "captions", "state", "thumbnails"):
            paths[key].mkdir(parents=True, exist_ok=True)

        summary = workspace.get_workspace_summary()
        saved_control_count = int(summary.get("settings", {}).get("control_count", 1) if control_count is None else control_count)
        saved_control_count = max(0, min(3, saved_control_count))
        active_roles = _active_roles(saved_control_count)
        old_by_name, old_by_source = _old_asset_maps(project_dir)
        used: set[str] = set()
        keep_files: set[Path] = set()
        manifest_items: list[dict] = []
        workspace_items: list[dict] = []
        label_items: dict[str, list[str]] = {}
        cover = ""

        for item in items:
            source_name = str(item.get("name", "item") or "item")
            item_id = _item_target_stem(source_name, used)
            item_assets: dict[str, str] = {}
            row_roles: dict[str, str] = {}
            item_paths = item.get("paths", {}) if isinstance(item.get("paths"), dict) else {}

            for role in active_roles:
                source_value = str(item_paths.get(role, "") or "")
                source = Path(source_value) if source_value else None
                target_rel = ""
                if source and source.is_file():
                    suffix = source.suffix.lower()
                    target = paths["assets"] / role / f"{item_id}{suffix}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if source.resolve() != target.resolve():
                        shutil.copy2(source, target)
                    target_rel = _relative(target, project_dir)
                else:
                    previous_rel = old_by_name.get((item_id, role)) or old_by_source.get((source_name, role))
                    previous_path = (project_dir / previous_rel).resolve() if previous_rel else None
                    if previous_path and previous_path.is_file() and is_relative_to(previous_path, project_dir):
                        target_rel = previous_rel
                    elif item.get("exists", {}).get(role):
                        raise FileNotFoundError(f"Project item source image missing: {source_name} ({role})")

                if target_rel:
                    keep_files.add((project_dir / target_rel).resolve())
                    item_assets[role] = target_rel
                    row_roles[role] = target_rel
                    if not cover and role == "result":
                        cover = target_rel
                    elif not cover:
                        cover = target_rel

            caption = str(item.get("text", "") or "")
            caption_rel = f"captions/{item_id}.txt"
            caption_path = project_dir / caption_rel
            caption_path.parent.mkdir(parents=True, exist_ok=True)
            if caption:
                caption_path.write_text(caption, encoding="utf-8")
                keep_files.add(caption_path.resolve())
                result_caption = paths["assets"] / "result" / f"{item_id}.txt"
                result_caption.parent.mkdir(parents=True, exist_ok=True)
                result_caption.write_text(caption, encoding="utf-8")
                keep_files.add(result_caption.resolve())
            else:
                if caption_path.exists():
                    caption_path.unlink()
                result_caption = paths["assets"] / "result" / f"{item_id}.txt"
                if result_caption.exists():
                    result_caption.unlink()

            status = "captioned" if caption.strip() else "pending"
            manifest_items.append(
                {
                    "id": item_id,
                    "display_name": item_id,
                    "source_name": source_name,
                    "assets": item_assets,
                    "caption_path": caption_rel,
                    "status": status,
                    "updated_at": _now(),
                }
            )
            if isinstance(item.get("tags", []), list):
                label_items[item_id] = item.get("tags", [])
            workspace_items.append(
                {
                    "name": item_id,
                    "source_name": source_name,
                    "roles": row_roles,
                    "caption": caption,
                }
            )

        _cleanup_project_assets(project_dir, active_roles, keep_files)
        if paths["captions"].is_dir():
            for path in sorted(paths["captions"].rglob("*"), reverse=True):
                if path.is_file() and path.resolve() not in keep_files:
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        pass

        now = _now()
        project_name = _clean_name(name or existing_meta.get("name") or project_id)
        project_meta = {
            "schema_version": SCHEMA_VERSION,
            "id": project_id,
            "name": project_name,
            "created_at": existing_meta.get("created_at") or now,
            "updated_at": now,
            "source_dirs": summary.get("dirs", {}),
            "item_count": len(manifest_items),
            "captioned_count": _captioned_count(workspace_items),
            "control_count": saved_control_count,
            "thumbnail": cover,
        }
        manifest = {"schema_version": SCHEMA_VERSION, "items": manifest_items}
        dirs = {
            role: str((public_paths["assets"] / role).resolve())
            for role in active_roles
            if (paths["assets"] / role).exists()
        }
        workspace_settings = dict(summary.get("settings", {}))
        workspace_settings["control_count"] = saved_control_count
        workspace_state = {
            "schema_version": SCHEMA_VERSION,
            "project_id": project_id,
            "project_name": project_name,
            "settings": workspace_settings,
            "dirs": dirs,
            "items": workspace_items,
            "ui_state": ui_state if isinstance(ui_state, dict) else {},
        }
        progress = {
            "schema_version": SCHEMA_VERSION,
            "total": len(manifest_items),
            "captioned": _captioned_count(workspace_items),
            "items": {
                item["id"]: {"status": item["status"], "updated_at": item["updated_at"]}
                for item in manifest_items
            },
        }
        labels = {
            "schema_version": SCHEMA_VERSION,
            "items": label_items,
        }

        _write_json(paths["project"], project_meta)
        _write_json(paths["manifest"], manifest)
        _write_json(paths["workspace"], workspace_state)
        _write_json(paths["state"] / "progress.json", progress)
        _write_json(paths["state"] / "labels.json", labels)
        _write_json(paths["state"] / "caption_config.json", workspace_state["ui_state"].get("caption_settings", {}))
        _write_json(paths["state"] / "ui_state.json", workspace_state["ui_state"])
        if staging_dir is not None:
            _sync_directory_contents(staging_dir, final_project_dir)
            shutil.rmtree(staging_dir, ignore_errors=True)
            self._cleanup_tmp_projects(project_id)
        self._refresh_index()
        return {"project": project_meta, "workspace": workspace_state}

    def rename_project(self, project_id: str, name: str) -> dict:
        path = self._project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        next_id = _renamed_project_id(project_id, name)
        next_path = self._project_dir(next_id)
        index = 2
        while next_path.exists() and next_path != path:
            next_id = f"{_renamed_project_id(project_id, name)}-{index}"
            next_path = self._project_dir(next_id)
            index += 1
        if next_path != path:
            path.replace(next_path)
            path = next_path

        meta = _read_json(path / "project.json", {})
        meta["id"] = next_id
        meta["name"] = _clean_name(name)
        meta["updated_at"] = _now()
        _write_json(path / "project.json", meta)
        workspace = _read_json(path / "workspace.json", {})
        workspace["project_id"] = next_id
        workspace["project_name"] = meta["name"]
        workspace["dirs"] = _workspace_dirs(path, int(meta.get("control_count", 1)))
        _write_json(path / "workspace.json", workspace)
        self._refresh_index()
        return meta

    def clone_project(self, project_id: str, name: str = "") -> dict:
        self.ensure()
        source = self._project_dir(project_id)
        if not source.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        source_meta = _read_json(source / "project.json", {})
        clone_name = _clean_name(name or f"{source_meta.get('name') or project_id} 副本")
        clone_id, clone_dir = self._unique_project_dir(clone_name)
        shutil.copytree(source, clone_dir)
        now = _now()
        meta = _read_json(clone_dir / "project.json", {})
        meta.update({"id": clone_id, "name": clone_name, "created_at": now, "updated_at": now})
        _write_json(clone_dir / "project.json", meta)
        workspace = _read_json(clone_dir / "workspace.json", {})
        workspace["project_id"] = clone_id
        workspace["project_name"] = clone_name
        workspace["dirs"] = _workspace_dirs(clone_dir, int(meta.get("control_count", 1)))
        _write_json(clone_dir / "workspace.json", workspace)
        self._refresh_index()
        return {"project": meta, "workspace": workspace}

    def update_ui_state(self, project_id: str, ui_state: dict) -> dict:
        path = self._project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        workspace = _read_json(path / "workspace.json", {})
        workspace["ui_state"] = ui_state if isinstance(ui_state, dict) else {}
        _write_json(path / "workspace.json", workspace)
        _write_json(path / "state" / "caption_config.json", workspace["ui_state"].get("caption_settings", {}))
        _write_json(path / "state" / "ui_state.json", workspace["ui_state"])
        meta = _read_json(path / "project.json", {})
        meta["updated_at"] = _now()
        _write_json(path / "project.json", meta)
        self._refresh_index()
        return {"project": meta, "workspace": workspace}

    def delete_project(self, project_id: str) -> dict:
        path = self._project_dir(project_id)
        if not path.is_dir():
            raise FileNotFoundError(f"Project not found: {project_id}")
        target = (self.trash_dir / f"{project_id}-{_now_id()}").resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        path.replace(target)
        self._refresh_index()
        return {"deleted": project_id, "trashed_to": str(target)}
