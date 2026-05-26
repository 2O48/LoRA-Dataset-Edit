from __future__ import annotations

import argparse
import io
import json
import socket
import sys
import threading
import time
from collections import OrderedDict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urlparse

from PIL import Image

SERVER_DIR = Path(__file__).resolve().parent
BASE_DIR = SERVER_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from api_caption_client import APICaptionClient
from caption_client import CaptionServiceClient, DependencyInstaller
from server.caption_workflow import (
    BatchCaptionManager,
    VALIDATION_EXISTING_CAPTION,
    apply_caption_result as _apply_caption_result,
    caption_with_backend as _caption_with_backend,
    collect_item_images as _collect_item_images,
    create_validation_images as _create_validation_images,
    normalize_overwrite_mode as _normalize_overwrite_mode,
    remove_validation_images as _remove_validation_images,
    resolve_caption_request as _resolve_caption_request,
)
from dataset_exporter import export_dataset
from dataset_image_processor import (
    process_viewer_item_match_result,
    process_viewer_item_scale,
)
from dataset_paths import cleanup_tmp, ensure_dataset_dirs, is_relative_to
from dataset_projects import ProjectStore
from dataset_workspace import DatasetWorkspace, IMAGE_EXTS, _resolve_user_path
from server.image_process_jobs import ImageProcessManager
from ollama_caption_client import OllamaCaptionClient
from prompt_templates import PromptTemplateStore
from qwen_models import list_qwen_model_configs


INDEX_FILE = BASE_DIR / "web_index.html"
APP_JS_FILE = BASE_DIR / "web_app.js"
STYLES_FILE = BASE_DIR / "web_styles.css"
PROMPT_TEMPLATES_FILE = BASE_DIR / "prompt_templates.json"
THUMB_CACHE_MAX_ITEMS = 256


WORKSPACE = DatasetWorkspace()
CAPTION_CLIENT = CaptionServiceClient()
API_CAPTION_CLIENT = APICaptionClient()
OLLAMA_CAPTION_CLIENT = OllamaCaptionClient()
DEPENDENCY_INSTALLER = DependencyInstaller()
PROMPT_TEMPLATES = PromptTemplateStore(PROMPT_TEMPLATES_FILE)
PROJECT_STORE = ProjectStore()
THUMB_CACHE_LOCK = threading.RLock()
THUMB_CACHE: OrderedDict[tuple[str, int, int, int], bytes] = OrderedDict()


def _download_content_disposition(filename: str) -> str:
    fallback = (filename or "dataset.zip").encode("ascii", "ignore").decode("ascii").strip()
    fallback = fallback.replace("\\", "_").replace("/", "_").replace('"', "_") or "dataset.zip"
    encoded = quote(filename or fallback)
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def _thumbnail_cache_key(path: Path, width: int, height: int) -> tuple[str, int, int, int]:
    stat = path.stat()
    return (str(path), int(stat.st_mtime_ns), int(width), int(height))


def _get_cached_thumbnail(key: tuple[str, int, int, int]) -> Optional[bytes]:
    with THUMB_CACHE_LOCK:
        data = THUMB_CACHE.get(key)
        if data is None:
            return None
        THUMB_CACHE.move_to_end(key)
        return data


def _store_cached_thumbnail(key: tuple[str, int, int, int], data: bytes):
    with THUMB_CACHE_LOCK:
        THUMB_CACHE[key] = data
        THUMB_CACHE.move_to_end(key)
        while len(THUMB_CACHE) > THUMB_CACHE_MAX_ITEMS:
            THUMB_CACHE.popitem(last=False)


BATCH_MANAGER = BatchCaptionManager(WORKSPACE, CAPTION_CLIENT, API_CAPTION_CLIENT, OLLAMA_CAPTION_CLIENT)
IMAGE_PROCESS_MANAGER = ImageProcessManager(WORKSPACE)


def _list_child_directories(path_value: str) -> dict:
    if not (path_value or "").strip():
        raise ValueError("Missing directory path.")
    root = _resolve_user_path(path_value)
    if not root.exists():
        raise FileNotFoundError(f"Directory does not exist: {path_value}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {path_value}")

    items: list[dict] = []
    child_dirs = (
        item
        for item in root.iterdir()
        if item.is_dir() and not item.name.startswith(".") and item.name != "__pycache__"
    )
    for child in sorted(child_dirs, key=lambda item: item.name.lower()):
        image_count = 0
        try:
            image_count = sum(1 for item in child.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_EXTS)
        except Exception:
            image_count = 0
        items.append(
            {
                "name": child.name,
                "path": str(child),
                "image_count": image_count,
            }
        )

    return {
        "path": str(root),
        "parent": str(root.parent) if root.parent != root else "",
        "items": items,
    }


def _project_thumbnail_path(project_id: str) -> Path:
    detail = PROJECT_STORE.get_project(project_id)
    project_dir = Path(detail["path"]).resolve()
    thumb = str(detail["project"].get("thumbnail", "") or "")
    if not thumb:
        raise FileNotFoundError("Project has no thumbnail.")
    path = (project_dir / thumb).resolve()
    if not is_relative_to(path, project_dir) or not path.is_file():
        raise FileNotFoundError("Project thumbnail not found.")
    return path


def _tmp_cleanup_loop():
    while True:
        time.sleep(24 * 3600)
        cleanup_tmp()


class AppHandler(BaseHTTPRequestHandler):
    server_version = "LoRADataEditHTTP/1.0"

    def log_message(self, format, *args):
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200, headers: Optional[dict[str, str]] = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status)

    def _send_text_file(self, path: Path, content_type: str):
        self._send_bytes(path.read_bytes(), content_type)

    def _error(self, message: str, status: int = 400):
        self._send_json({"ok": False, "error": message}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/":
                return self._send_text_file(INDEX_FILE, "text/html; charset=utf-8")
            if path == "/app.js":
                return self._send_text_file(APP_JS_FILE, "text/javascript; charset=utf-8")
            if path.startswith("/frontend/") and path.endswith(".js"):
                target = (BASE_DIR / path.lstrip("/")).resolve()
                if not is_relative_to(target, BASE_DIR) or not target.is_file():
                    return self._error(f"Unknown route: {path}", status=404)
                return self._send_text_file(target, "text/javascript; charset=utf-8")
            if path == "/styles.css":
                return self._send_text_file(STYLES_FILE, "text/css; charset=utf-8")
            if path == "/api/workspace":
                return self._send_json({"ok": True, "workspace": WORKSPACE.get_workspace_summary()})
            if path == "/api/workspace/browse":
                browse_path = query.get("path", [""])[0]
                return self._send_json({"ok": True, "browser": _list_child_directories(browse_path)})
            if path == "/api/projects":
                return self._send_json({"ok": True, "projects": PROJECT_STORE.list_projects()})
            if path == "/api/projects/detail":
                project_id = query.get("id", [""])[0]
                return self._send_json({"ok": True, **PROJECT_STORE.get_project(project_id)})
            if path == "/api/projects/thumbnail":
                project_id = query.get("id", [""])[0]
                path_value = _project_thumbnail_path(project_id)
                return self._send_project_thumbnail(path_value, query)
            if path == "/api/items":
                filter_mode = query.get("filter", ["all"])[0]
                tag_query = query.get("tag", [""])[0]
                detail = query.get("detail", ["0"])[0] in {"1", "true", "yes"}
                data = WORKSPACE.list_items(filter_mode=filter_mode, tag_query=tag_query, detail=detail)
                return self._send_json({"ok": True, **data})
            if path == "/api/item":
                name = query.get("name", [""])[0]
                if not name:
                    return self._error("Missing item name.")
                return self._send_json({"ok": True, "item": WORKSPACE.get_item(name)})
            if path == "/api/image":
                return self._handle_image(query)
            if path == "/api/ai/options":
                return self._send_json(
                    {
                        "ok": True,
                        "local_models": list_qwen_model_configs(),
                        "default_local_model": "qwen3.5-4b",
                        "default_ollama_url": "http://127.0.0.1:11434",
                    }
                )
            if path == "/api/ollama/models":
                base_url = query.get("base_url", ["http://127.0.0.1:11434"])[0]
                models = OLLAMA_CAPTION_CLIENT.list_models(base_url)
                return self._send_json({"ok": True, "models": models})
            if path == "/api/prompt-templates":
                return self._send_json({"ok": True, "templates": PROMPT_TEMPLATES.load()})
            if path == "/api/ai/status":
                return self._send_json(
                    {
                        "ok": True,
                        "service": CAPTION_CLIENT.snapshot(),
                        "api_service": API_CAPTION_CLIENT.snapshot(),
                        "ollama_service": OLLAMA_CAPTION_CLIENT.snapshot(),
                        "installer": DEPENDENCY_INSTALLER.snapshot(),
                        "batch": BATCH_MANAGER.snapshot(),
                        "image_process": IMAGE_PROCESS_MANAGER.snapshot(),
                    }
                )
            if path == "/api/images/process/status":
                return self._send_json({"ok": True, "image_process": IMAGE_PROCESS_MANAGER.snapshot()})
            return self._error(f"Unknown route: {path}", status=404)
        except KeyError as exc:
            return self._error(f"Item not found: {exc}", status=404)
        except Exception as exc:
            return self._error(str(exc), status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json()
        except Exception as exc:
            return self._error(f"Invalid JSON body: {exc}")

        try:
            if path == "/api/workspace/open":
                summary = WORKSPACE.open_dirs(
                    control1_dir=body.get("control1_dir") or None,
                    control2_dir=body.get("control2_dir") or None,
                    control3_dir=body.get("control3_dir") or None,
                    result_dir=body.get("result_dir") or None,
                    control_count=body.get("control_count"),
                    ignore_tokens=body.get("ignore_tokens"),
                )
                IMAGE_PROCESS_MANAGER.reset_if_idle()
                return self._send_json({"ok": True, "workspace": summary})

            if path == "/api/workspace/rescan":
                summary = WORKSPACE.open_dirs()
                return self._send_json({"ok": True, "workspace": summary})

            if path == "/api/workspace/merge":
                result = WORKSPACE.merge_dirs(
                    control1_dir=body.get("control1_dir") or None,
                    control2_dir=body.get("control2_dir") or None,
                    control3_dir=body.get("control3_dir") or None,
                    result_dir=body.get("result_dir") or None,
                    control_count=body.get("control_count"),
                )
                return self._send_json({"ok": True, **result})

            if path == "/api/projects/save":
                result = PROJECT_STORE.save_project(
                    name=str(body.get("name", "") or ""),
                    workspace=WORKSPACE,
                    overwrite_id=str(body.get("overwrite_id", "") or ""),
                    control_count=body.get("control_count"),
                    ui_state=body.get("ui_state", {}),
                )
                workspace = result.get("workspace", {}) if isinstance(result.get("workspace"), dict) else {}
                dirs = workspace.get("dirs", {}) if isinstance(workspace.get("dirs"), dict) else {}
                settings = workspace.get("settings", {}) if isinstance(workspace.get("settings"), dict) else {}
                summary = WORKSPACE.open_dirs(
                    control1_dir=dirs.get("control1") or "",
                    control2_dir=dirs.get("control2") or "",
                    control3_dir=dirs.get("control3") or "",
                    result_dir=dirs.get("result") or "",
                    control_count=settings.get("control_count", result.get("project", {}).get("control_count", 1)),
                    ignore_tokens=settings.get("ignore_tokens", []),
                )
                items = workspace.get("items", []) if isinstance(workspace.get("items"), list) else []
                aliases = {
                    str(item.get("name", "") or ""): str(item.get("source_name", "") or "")
                    for item in items
                    if isinstance(item, dict) and item.get("name") and item.get("source_name")
                }
                if aliases:
                    summary = WORKSPACE.apply_name_aliases(aliases)
                result["workspace"] = summary
                return self._send_json({"ok": True, **result})

            if path == "/api/projects/open":
                project_id = str(body.get("id", "") or "")
                detail = PROJECT_STORE.get_project(project_id)
                workspace = detail.get("workspace", {})
                dirs = workspace.get("dirs", {}) if isinstance(workspace.get("dirs"), dict) else {}
                settings = workspace.get("settings", {}) if isinstance(workspace.get("settings"), dict) else {}
                summary = WORKSPACE.open_dirs(
                    control1_dir=dirs.get("control1") or "",
                    control2_dir=dirs.get("control2") or "",
                    control3_dir=dirs.get("control3") or "",
                    result_dir=dirs.get("result") or "",
                    control_count=settings.get("control_count", detail.get("project", {}).get("control_count", 1)),
                    ignore_tokens=settings.get("ignore_tokens", []),
                )
                items = workspace.get("items", []) if isinstance(workspace.get("items"), list) else []
                aliases = {
                    str(item.get("name", "") or ""): str(item.get("source_name", "") or "")
                    for item in items
                    if isinstance(item, dict) and item.get("name") and item.get("source_name")
                }
                if aliases:
                    summary = WORKSPACE.apply_name_aliases(aliases)
                IMAGE_PROCESS_MANAGER.reset_if_idle()
                return self._send_json({
                    "ok": True,
                    "workspace": summary,
                    "project": detail.get("project", {}),
                    "ui_state": workspace.get("ui_state", {}) if isinstance(workspace.get("ui_state"), dict) else {},
                })

            if path == "/api/projects/rename":
                project = PROJECT_STORE.rename_project(str(body.get("id", "") or ""), str(body.get("name", "") or ""))
                return self._send_json({"ok": True, "project": project})

            if path == "/api/projects/clone":
                result = PROJECT_STORE.clone_project(
                    str(body.get("id", "") or ""),
                    str(body.get("name", "") or ""),
                )
                return self._send_json({"ok": True, **result})

            if path == "/api/projects/ui-state":
                result = PROJECT_STORE.update_ui_state(
                    str(body.get("id", "") or ""),
                    body.get("ui_state", {}),
                )
                return self._send_json({"ok": True, **result})

            if path == "/api/projects/delete":
                result = PROJECT_STORE.delete_project(str(body.get("id", "") or ""))
                return self._send_json({"ok": True, **result})

            if path == "/api/tmp/cleanup":
                result = cleanup_tmp(max_age_hours=int(body.get("max_age_hours", 48) or 48))
                return self._send_json({"ok": True, "cleanup": result})

            if path == "/api/item/save":
                name = body.get("name", "")
                if "text" in body:
                    item = WORKSPACE.save_text(name, str(body.get("text", "")))
                else:
                    segments = body.get("segments", body.get("tags", []))
                    if not isinstance(segments, list):
                        return self._error("segments must be a list.")
                    item = WORKSPACE.save_segments(name, segments)
                return self._send_json({"ok": True, "item": item})

            if path == "/api/item/delete":
                name = body.get("name", "")
                result = WORKSPACE.delete_item(name)
                return self._send_json({"ok": True, **result})

            if path in {"/api/batch/add", "/api/batch/add-segments"}:
                result = WORKSPACE.batch_add_segments(body.get("names", []), body.get("segments", body.get("tags", [])))
                return self._send_json({"ok": True, **result})

            if path in {"/api/batch/delete", "/api/batch/delete-segments"}:
                result = WORKSPACE.batch_delete_segments(body.get("names", []), body.get("segments", body.get("tags", [])))
                return self._send_json({"ok": True, **result})

            if path in {"/api/batch/replace", "/api/batch/replace-segment"}:
                result = WORKSPACE.batch_replace_segment(
                    body.get("names", []),
                    body.get("old_segment", body.get("old_tag", "")),
                    body.get("new_segment", body.get("new_tag", "")),
                )
                return self._send_json({"ok": True, **result})

            if path == "/api/export/dataset":
                names = body.get("names", [])
                if names is not None and not isinstance(names, list):
                    return self._error("names must be a list.")
                export_result = export_dataset(
                    items=WORKSPACE.get_export_items(names or None),
                    output_format=str(body.get("format", "zip") or "zip"),
                    output_dir=str(body.get("output_dir", "") or ""),
                    project_name=str(body.get("project_name", "") or ""),
                    target_megapixels=float(body.get("target_megapixels", 4.0) or 4.0),
                    multiple=int(body.get("multiple", 16) or 16),
                    process_images=bool(body.get("process_images", True)),
                    include_controls=bool(body.get("include_controls", True)),
                    control_count=WORKSPACE.control_count,
                )
                if export_result["format"] == "zip":
                    filename = export_result.get("filename", "dataset.zip")
                    return self._send_bytes(
                        export_result["bytes"],
                        "application/zip",
                        headers={"Content-Disposition": _download_content_disposition(filename)},
                    )
                return self._send_json({"ok": True, "export": export_result})

            if path == "/api/images/process/start":
                IMAGE_PROCESS_MANAGER.start(
                    options={
                        "mode": "process",
                        "output_dir": str(body.get("output_dir", "") or ""),
                        "project_name": str(body.get("project_name", "") or ""),
                        "target_megapixels": float(body.get("target_megapixels", 4.0) or 4.0),
                        "multiple": int(body.get("multiple", 16) or 16),
                        "include_controls": bool(body.get("include_controls", True)),
                        "load_workspace": bool(body.get("load_workspace", True)),
                    }
                )
                return self._send_json({"ok": True, "image_process": IMAGE_PROCESS_MANAGER.snapshot()})

            if path == "/api/images/match-result/start":
                IMAGE_PROCESS_MANAGER.start(
                    options={
                        "mode": "match_result",
                        "output_dir": str(body.get("output_dir", "") or ""),
                        "project_name": str(body.get("project_name", "") or ""),
                        "include_controls": bool(body.get("include_controls", True)),
                        "load_workspace": bool(body.get("load_workspace", True)),
                        "only_mismatched": bool(body.get("only_mismatched", True)),
                    }
                )
                return self._send_json({"ok": True, "image_process": IMAGE_PROCESS_MANAGER.snapshot()})

            if path == "/api/images/process":
                process_result = process_workspace_images(
                    items=WORKSPACE.get_export_items(),
                    output_dir=str(body.get("output_dir", "") or ""),
                    project_name=str(body.get("project_name", "") or ""),
                    target_megapixels=float(body.get("target_megapixels", 4.0) or 4.0),
                    multiple=int(body.get("multiple", 16) or 16),
                    include_controls=bool(body.get("include_controls", True)),
                    control_count=WORKSPACE.control_count,
                )
                payload = {"ok": True, "process": process_result}
                if bool(body.get("load_workspace", True)):
                    dirs = process_result.get("dirs", {})
                    summary = WORKSPACE.open_dirs(
                        control1_dir=dirs.get("control1") or "",
                        control2_dir=dirs.get("control2") or "",
                        control3_dir=dirs.get("control3") or "",
                        result_dir=dirs.get("result") or "",
                        control_count=WORKSPACE.control_count,
                        ignore_tokens=WORKSPACE.ignore_tokens,
                    )
                    payload["workspace"] = summary
                return self._send_json(payload)

            if path == "/api/images/item/scale":
                name = str(body.get("name", "") or "")
                if not name:
                    return self._error("Missing item name.")
                item = WORKSPACE.get_item(name)
                process_result = process_viewer_item_scale(
                    item=item,
                    target_megapixels=float(body.get("target_megapixels", 4.0) or 4.0),
                    control_count=WORKSPACE.control_count,
                )
                updated = WORKSPACE.replace_item_paths(name, process_result.get("paths", {}))
                return self._send_json({"ok": True, "process": process_result, "item": updated})

            if path == "/api/images/item/match-result":
                name = str(body.get("name", "") or "")
                if not name:
                    return self._error("Missing item name.")
                item = WORKSPACE.get_item(name)
                process_result = process_viewer_item_match_result(
                    item=item,
                    control_count=WORKSPACE.control_count,
                )
                updated = WORKSPACE.replace_item_paths(name, process_result.get("paths", {}))
                return self._send_json({"ok": True, "process": process_result, "item": updated})

            if path == "/api/translate":
                text = body.get("text", "")
                translated = WORKSPACE.translate_text(text)
                return self._send_json({"ok": True, "translated": translated})

            if path == "/api/prompt-templates/save":
                templates = PROMPT_TEMPLATES.save_template(
                    name=body.get("name", ""),
                    content=body.get("content", ""),
                )
                return self._send_json({"ok": True, "templates": templates})

            if path == "/api/prompt-templates/delete":
                templates = PROMPT_TEMPLATES.delete_template(body.get("id", ""))
                return self._send_json({"ok": True, "templates": templates})

            if path == "/api/api/models":
                models = API_CAPTION_CLIENT.list_models(
                    api_base_url=body.get("api_base_url", ""),
                    api_key=body.get("api_key", ""),
                )
                return self._send_json({"ok": True, "models": models})

            if path == "/api/ai/install":
                started = DEPENDENCY_INSTALLER.start()
                return self._send_json({"ok": True, "started": started, "installer": DEPENDENCY_INSTALLER.snapshot()})

            if path == "/api/ai/load":
                model = body.get("model", "qwen3.5-4b")
                CAPTION_CLIENT.load_model(model)
                return self._send_json({"ok": True, "service": CAPTION_CLIENT.snapshot()})

            if path == "/api/ai/caption":
                name = body.get("name", "")
                if not name:
                    return self._error("Missing item name.")
                item = WORKSPACE.get_item(name)
                overwrite_mode = _normalize_overwrite_mode(body.get("overwrite_mode", "overwrite"))
                if item["exists"]["txt"] and overwrite_mode == "skip":
                    return self._send_json({"ok": True, "result": item["text"], "item": item, "skipped": True})
                image_paths = _collect_item_images(item, control_count=WORKSPACE.control_count)
                if not image_paths:
                    return self._error("No image found for this item.")
                backend = str(body.get("backend", "local") or "local")
                model = body.get("model", "qwen3.5-4b")
                request = _resolve_caption_request(item["text"], body.get("prompt", ""), overwrite_mode=overwrite_mode)
                result = _caption_with_backend(
                    backend=backend,
                    image_paths=image_paths,
                    image_name=name,
                    model=model,
                    mode=body.get("mode", "natural"),
                    prompt=request["prompt"],
                    max_tokens=int(body.get("max_tokens", 512)),
                    thinking=bool(body.get("thinking", False)),
                    api_base_url=body.get("api_base_url", ""),
                    api_key=body.get("api_key", ""),
                    ollama_base_url=body.get("ollama_base_url", "http://127.0.0.1:11434"),
                    local_client=CAPTION_CLIENT,
                    api_client=API_CAPTION_CLIENT,
                    ollama_client=OLLAMA_CAPTION_CLIENT,
                )
                output_text = _apply_caption_result(item["text"], result, request["write_mode"])
                updated = WORKSPACE.save_text(name, output_text)
                return self._send_json(
                    {
                        "ok": True,
                        "result": result,
                        "item": updated,
                        "used_modify": request["used_modify"],
                        "fallback_to_overwrite": request["fallback_to_overwrite"],
                    }
                )

            if path == "/api/ai/validate":
                backend = str(body.get("backend", "local") or "local")
                model = body.get("model", "qwen3.5-4b")
                overwrite_mode = _normalize_overwrite_mode(body.get("overwrite_mode", "overwrite"))
                validation_request = _resolve_caption_request(
                    VALIDATION_EXISTING_CAPTION,
                    body.get("prompt", ""),
                    overwrite_mode=overwrite_mode,
                )
                if backend == "api":
                    validation = API_CAPTION_CLIENT.validate(
                        api_base_url=body.get("api_base_url", ""),
                        api_key=body.get("api_key", ""),
                        model=str(model),
                        mode=body.get("mode", "natural"),
                        prompt=validation_request["prompt"],
                        max_tokens=int(body.get("max_tokens", 128)),
                    )
                elif backend == "ollama":
                    validation = OLLAMA_CAPTION_CLIENT.validate(
                        base_url=body.get("ollama_base_url", "http://127.0.0.1:11434"),
                        model=str(model),
                        mode=body.get("mode", "natural"),
                        prompt=validation_request["prompt"],
                        max_tokens=int(body.get("max_tokens", 128)),
                    )
                else:
                    validation_images = _create_validation_images()
                    try:
                        result = _caption_with_backend(
                            backend="local",
                            image_paths=validation_images,
                            model=str(model),
                            mode=body.get("mode", "natural"),
                            prompt=validation_request["prompt"] or "Describe the visual change from the first image to the second image in one short sentence.",
                            max_tokens=int(body.get("max_tokens", 128)),
                            thinking=bool(body.get("thinking", False)),
                            api_base_url="",
                            api_key="",
                            ollama_base_url="",
                            local_client=CAPTION_CLIENT,
                            api_client=API_CAPTION_CLIENT,
                            ollama_client=OLLAMA_CAPTION_CLIENT,
                        )
                        validation = {
                            "ok": True,
                            "result": result,
                            "backend": "local",
                            "model": model,
                        }
                    finally:
                        _remove_validation_images(validation_images)
                if overwrite_mode == "modify":
                    validation["existing_text"] = VALIDATION_EXISTING_CAPTION
                    validation["used_modify"] = True
                return self._send_json({"ok": True, "validation": validation})

            if path == "/api/ai/batch/start":
                names = body.get("names", [])
                if not isinstance(names, list) or not names:
                    return self._error("Batch requires a non-empty names list.")
                BATCH_MANAGER.start(
                    names=names,
                    options={
                        "backend": body.get("backend", "local"),
                        "model": body.get("model", "qwen3.5-4b"),
                        "overwrite_mode": body.get("overwrite_mode", "skip"),
                        "mode": body.get("mode", "natural"),
                        "prompt": body.get("prompt", ""),
                        "max_tokens": int(body.get("max_tokens", 512)),
                        "thinking": bool(body.get("thinking", False)),
                        "api_base_url": body.get("api_base_url", ""),
                        "api_key": body.get("api_key", ""),
                        "ollama_base_url": body.get("ollama_base_url", "http://127.0.0.1:11434"),
                    },
                )
                return self._send_json({"ok": True, "batch": BATCH_MANAGER.snapshot()})

            if path == "/api/ai/batch/stop":
                BATCH_MANAGER.stop()
                load_cancelled = CAPTION_CLIENT.cancel_load()
                return self._send_json({
                    "ok": True,
                    "batch": BATCH_MANAGER.snapshot(),
                    "service": CAPTION_CLIENT.snapshot(),
                    "load_cancelled": load_cancelled,
                })

            return self._error(f"Unknown route: {path}", status=404)
        except KeyError as exc:
            return self._error(f"Item not found: {exc}", status=404)
        except RuntimeError as exc:
            return self._error(str(exc), status=400)
        except TimeoutError as exc:
            return self._error(str(exc), status=504)
        except Exception as exc:
            return self._error(str(exc), status=500)

    def _handle_image(self, query: dict[str, list[str]]):
        role = query.get("role", ["result"])[0]
        name = query.get("name", [""])[0]
        thumb = query.get("thumb", ["0"])[0] == "1"
        width = int(query.get("width", ["320"])[0])
        height = int(query.get("height", ["220"])[0])

        if not name:
            return self._error("Missing item name.")
        path = WORKSPACE.resolve_image_path(role, name)
        if not path or not path.exists():
            return self._error("Image not found.", status=404)

        if not thumb:
            suffix = path.suffix.lower()
            content_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
                ".tiff": "image/tiff",
                ".avif": "image/avif",
            }.get(suffix, "application/octet-stream")
            return self._send_bytes(path.read_bytes(), content_type)

        cache_key = _thumbnail_cache_key(path, max(width, 32), max(height, 32))
        cached = _get_cached_thumbnail(cache_key)
        if cached is not None:
            return self._send_bytes(cached, "image/jpeg")

        with Image.open(path) as img:
            if img.mode not in {"RGB", "RGBA"}:
                img = img.convert("RGB")
            img.thumbnail((cache_key[2], cache_key[3]))
            if img.mode == "RGBA":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
        data = buf.getvalue()
        _store_cached_thumbnail(cache_key, data)
        return self._send_bytes(data, "image/jpeg")

    def _send_project_thumbnail(self, path: Path, query: dict[str, list[str]]):
        width = int(query.get("width", ["420"])[0])
        height = int(query.get("height", ["260"])[0])
        cache_key = _thumbnail_cache_key(path, max(width, 32), max(height, 32))
        cached = _get_cached_thumbnail(cache_key)
        if cached is not None:
            return self._send_bytes(cached, "image/jpeg")

        with Image.open(path) as img:
            if img.mode not in {"RGB", "RGBA"}:
                img = img.convert("RGB")
            img.thumbnail((cache_key[2], cache_key[3]))
            if img.mode == "RGBA":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
        data = buf.getvalue()
        _store_cached_thumbnail(cache_key, data)
        return self._send_bytes(data, "image/jpeg")


def _get_bind_urls(host: str, port: int) -> list[str]:
    urls = [f"http://127.0.0.1:{port}"]
    if host in {"0.0.0.0", "::"}:
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and not local_ip.startswith("127."):
                urls.append(f"http://{local_ip}:{port}")
        except Exception:
            pass
    elif host not in {"127.0.0.1", "localhost"}:
        urls.append(f"http://{host}:{port}")
    return urls


def main():
    parser = argparse.ArgumentParser(description="LoRA Data Edit Web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    ensure_dataset_dirs()
    cleanup_tmp()
    threading.Thread(target=_tmp_cleanup_loop, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    urls = _get_bind_urls(args.host, args.port)
    print("LoRA Data Edit Web GUI is running.")
    for url in urls:
        print(f"  {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        CAPTION_CLIENT.stop()
        server.server_close()


if __name__ == "__main__":
    main()
