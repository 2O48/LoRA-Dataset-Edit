from __future__ import annotations

import json
import shutil
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATASETS_DIR = BASE_DIR / "datasets"
PROJECTS_DIR = DATASETS_DIR / "projects"
TMP_DIR = DATASETS_DIR / "tmp"
EXPORTS_DIR = DATASETS_DIR / "exports"
PROCESSED_DIR = DATASETS_DIR / "processed"
WORKSPACES_DIR = DATASETS_DIR / "workspaces"


def ensure_dataset_dirs() -> None:
    for path in (DATASETS_DIR, PROJECTS_DIR, TMP_DIR, EXPORTS_DIR, PROCESSED_DIR, WORKSPACES_DIR):
        path.mkdir(parents=True, exist_ok=True)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def cleanup_tmp(*, max_age_hours: int = 48) -> dict:
    ensure_dataset_dirs()
    now = time.time()
    max_age = max(1, int(max_age_hours or 48)) * 3600
    removed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for child in TMP_DIR.iterdir():
        try:
            if not child.exists():
                continue
            if child.is_file():
                if now - child.stat().st_mtime >= max_age:
                    child.unlink()
                    removed.append(child.name)
                continue
            if not child.is_dir():
                continue
            if (child / "job.lock").exists():
                skipped.append(child.name)
                continue
            job_file = child / "job.json"
            if job_file.exists():
                try:
                    job = json.loads(job_file.read_text(encoding="utf-8"))
                except Exception:
                    job = {}
                if str(job.get("status", "")).lower() == "running":
                    skipped.append(child.name)
                    continue
            if now - child.stat().st_mtime >= max_age:
                shutil.rmtree(child)
                removed.append(child.name)
        except Exception as exc:
            errors.append(f"{child.name}: {exc}")

    return {"removed": removed, "skipped": skipped, "errors": errors}
