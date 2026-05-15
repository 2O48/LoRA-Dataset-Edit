from __future__ import annotations

import threading
import time
from typing import Optional

from dataset_image_processor import process_workspace_images, process_workspace_match_results
from dataset_workspace import DatasetWorkspace


class ImageProcessManager:
    def __init__(self, workspace: DatasetWorkspace):
        self.workspace = workspace
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self.running = False
        self.total = 0
        self.done = 0
        self.processed = 0
        self.skipped = 0
        self.current = ""
        self.status = "idle"
        self.mode = "process"
        self.result: dict = {}
        self.workspace_loaded = False
        self.workspace_summary: dict = {}
        self.logs: list[dict] = []

    def _log(self, message: str, level: str = "info"):
        self.logs.append(
            {
                "ts": time.strftime("%H:%M:%S"),
                "level": level,
                "message": message,
            }
        )
        self.logs = self.logs[-300:]

    def snapshot(self) -> dict:
        with self._lock:
            pct = int((self.done / self.total) * 100) if self.total else (100 if self.status == "done" else 0)
            return {
                "running": self.running,
                "total": self.total,
                "done": self.done,
                "processed": self.processed,
                "skipped": self.skipped,
                "current": self.current,
                "status": self.status,
                "mode": self.mode,
                "progress_pct": max(0, min(pct, 100)),
                "result": dict(self.result),
                "workspace_loaded": self.workspace_loaded,
                "workspace": dict(self.workspace_summary),
                "logs": list(self.logs),
            }

    def start(self, *, options: dict):
        with self._lock:
            if self.running:
                raise RuntimeError("Image processing job is already running.")
            items = self.workspace.get_export_items()
            self.running = True
            self.total = len(items)
            self.done = 0
            self.processed = 0
            self.skipped = 0
            self.current = ""
            self.status = "running"
            self.mode = str(options.get("mode", "process") or "process")
            self.result = {}
            self.workspace_loaded = False
            self.workspace_summary = {}
            self.logs = []
            mode_label = "match-result" if self.mode == "match_result" else "process"
            self._log(f"Image processing started ({mode_label}). total={self.total}", "info")
            self._thread = threading.Thread(target=self._run, args=(items, dict(options)), daemon=True)
            self._thread.start()

    def reset_if_idle(self):
        with self._lock:
            if self.running:
                return
            self.total = 0
            self.done = 0
            self.processed = 0
            self.skipped = 0
            self.current = ""
            self.status = "idle"
            self.mode = "process"
            self.result = {}
            self.workspace_loaded = False
            self.workspace_summary = {}
            self.logs = []

    def _progress(self, row: dict):
        with self._lock:
            self.total = int(row.get("total", self.total) or self.total)
            self.done = int(row.get("done", self.done) or 0)
            self.processed = int(row.get("processed", self.processed) or 0)
            self.skipped = int(row.get("skipped", self.skipped) or 0)
            self.current = str(row.get("current", "") or "")
            message = str(row.get("message", "") or "")
            if message:
                self._log(message, str(row.get("level", "info") or "info"))

    def _run(self, items: list[dict], options: dict):
        try:
            control_count = self.workspace.control_count
            mode = str(options.get("mode", "process") or "process")
            if mode == "match_result":
                result = process_workspace_match_results(
                    items=items,
                    output_dir=str(options.get("output_dir", "") or ""),
                    project_name=str(options.get("project_name", "") or ""),
                    include_controls=bool(options.get("include_controls", True)),
                    only_mismatched=bool(options.get("only_mismatched", True)),
                    control_count=control_count,
                    progress_callback=self._progress,
                )
            else:
                result = process_workspace_images(
                    items=items,
                    output_dir=str(options.get("output_dir", "") or ""),
                    project_name=str(options.get("project_name", "") or ""),
                    target_megapixels=float(options.get("target_megapixels", 4.0) or 4.0),
                    multiple=int(options.get("multiple", 16) or 16),
                    include_controls=bool(options.get("include_controls", True)),
                    control_count=control_count,
                    progress_callback=self._progress,
                )
            with self._lock:
                self.result = result
                self.processed = int(result.get("processed", self.processed) or 0)
                self.skipped = len(result.get("skipped", []) or [])
                self.done = self.total
                self.current = ""
                self.status = "loading_workspace" if bool(options.get("load_workspace", True)) else "done"
                mode_label = "match-result" if mode == "match_result" else "process"
                self._log(f"Image processing done ({mode_label}). processed={self.processed} skipped={self.skipped}", "ok")

            if bool(options.get("load_workspace", True)):
                dirs = result.get("dirs", {})
                summary = self.workspace.open_dirs(
                    control1_dir=dirs.get("control1") or "",
                    control2_dir=dirs.get("control2") or "",
                    control3_dir=dirs.get("control3") or "",
                    result_dir=dirs.get("result") or "",
                    control_count=control_count,
                    ignore_tokens=self.workspace.ignore_tokens,
                )
                with self._lock:
                    self.workspace_loaded = True
                    self.workspace_summary = summary
                    self.status = "done"
                    self._log("Processed workspace loaded.", "ok")
        except Exception as exc:
            with self._lock:
                self.status = "error"
                self.current = ""
                self._log(str(exc), "error")
        finally:
            with self._lock:
                self.running = False
