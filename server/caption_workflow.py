from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from PIL import Image

from api_caption_client import APICaptionClient
from caption_client import CaptionServiceClient
from dataset_workspace import DatasetWorkspace
from ollama_caption_client import OllamaCaptionClient


VALIDATION_EXISTING_CAPTION = "woman standing near a window, soft natural light, blue dress, indoor portrait"


def normalize_overwrite_mode(value: str, fallback: str = "overwrite") -> str:
    mode = str(value or "").strip().lower()
    if mode in {"skip", "append", "modify", "overwrite"}:
        return mode
    return fallback


def build_modify_prompt(existing_text: str, instruction: str) -> str:
    clean_existing = (existing_text or "").strip()
    clean_instruction = (instruction or "").strip() or "Revise the existing caption so it matches the images more accurately."
    return (
        "You are editing an existing LoRA dataset caption.\n"
        "Update the caption according to the edit instruction and the images.\n"
        "Return only the revised final caption.\n\n"
        f"Existing caption:\n{clean_existing}\n\n"
        f"Edit instruction:\n{clean_instruction}"
    )


def resolve_caption_request(existing_text: str, prompt: str, *, overwrite_mode: str) -> dict:
    normalized = normalize_overwrite_mode(overwrite_mode)
    clean_existing = (existing_text or "").strip()
    if normalized == "modify" and clean_existing:
        return {
            "prompt": build_modify_prompt(clean_existing, prompt),
            "write_mode": "overwrite",
            "used_modify": True,
            "fallback_to_overwrite": False,
        }
    if normalized == "modify":
        return {
            "prompt": prompt,
            "write_mode": "overwrite",
            "used_modify": False,
            "fallback_to_overwrite": True,
        }
    return {
        "prompt": prompt,
        "write_mode": normalized,
        "used_modify": False,
        "fallback_to_overwrite": False,
    }


def apply_caption_result(existing_text: str, result: str, overwrite_mode: str) -> str:
    if overwrite_mode == "append" and existing_text:
        left = existing_text.strip()
        right = (result or "").strip()
        if not right:
            return left
        if not left:
            return right
        separator = "\n" if any(mark in right for mark in (".", "!", "?", "。", "！", "？")) else ", "
        return left.rstrip(",，;； ") + separator + right
    return result


def caption_with_backend(
    *,
    backend: str,
    image_paths: list[str],
    image_name: str = "",
    model,
    mode: str,
    prompt: str,
    max_tokens: int,
    thinking: bool,
    api_base_url: str,
    api_key: str,
    ollama_base_url: str,
    local_client: CaptionServiceClient,
    api_client: APICaptionClient,
    ollama_client: OllamaCaptionClient,
) -> str:
    image_file_names = [Path(path).name for path in image_paths if path]
    if backend == "api":
        return api_client.caption(
            image_path=image_paths[-1],
            image_paths=image_paths,
            image_name=image_name,
            image_file_names=image_file_names,
            api_base_url=api_base_url,
            api_key=api_key,
            model=str(model),
            mode=mode,
            prompt=prompt,
            max_tokens=max_tokens,
        )
    if backend == "ollama":
        return ollama_client.caption(
            image_path=image_paths[-1],
            image_paths=image_paths,
            image_name=image_name,
            image_file_names=image_file_names,
            base_url=ollama_base_url,
            model=str(model),
            mode=mode,
            prompt=prompt,
            max_tokens=max_tokens,
        )
    local_client.load_model(model)
    return local_client.caption(
        image_path=image_paths[-1],
        image_paths=image_paths,
        image_name=image_name,
        image_file_names=image_file_names,
        model=model,
        mode=mode,
        prompt=prompt,
        max_tokens=max_tokens,
        thinking=thinking,
    )


def create_validation_images() -> list[str]:
    paths: list[str] = []
    for color in ((214, 136, 78), (82, 126, 214)):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)
        Image.new("RGB", (96, 96), color).save(path)
        paths.append(str(path))
    return paths


def remove_validation_images(paths: list[str]):
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


def collect_item_images(item: dict, *, control_count: int = 3) -> list[str]:
    paths: list[str] = []
    count = 1 if control_count is None else int(control_count)
    for role in ("control1", "control2", "control3")[: max(0, min(3, count))]:
        value = item["paths"].get(role, "")
        if value:
            paths.append(value)
    result_path = item["paths"].get("result", "")
    if result_path:
        paths.append(result_path)
    return paths


class BatchCaptionManager:
    def __init__(
        self,
        workspace: DatasetWorkspace,
        client: CaptionServiceClient,
        api_client: APICaptionClient,
        ollama_client: OllamaCaptionClient,
    ):
        self.workspace = workspace
        self.client = client
        self.api_client = api_client
        self.ollama_client = ollama_client
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self.running = False
        self.stop_requested = False
        self.total = 0
        self.done = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.current = ""
        self.status = "idle"
        self.backend = "local"
        self.logs: list[dict] = []

    def _log(self, message: str, level: str = "info"):
        ts = time.strftime("%H:%M:%S")
        self.logs.append(
            {
                "ts": ts,
                "level": level,
                "message": message,
            }
        )
        self.logs = self.logs[-400:]
        print(f"[{ts}] [batch] [{level}] {message}", flush=True)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "stop_requested": self.stop_requested,
                "total": self.total,
                "done": self.done,
                "success": self.success,
                "failed": self.failed,
                "skipped": self.skipped,
                "current": self.current,
                "status": self.status,
                "backend": self.backend,
                "logs": list(self.logs),
            }

    def start(self, *, names: list[str], options: dict):
        with self._lock:
            if self.running:
                raise RuntimeError("Batch caption job is already running.")
            self.running = True
            self.stop_requested = False
            self.total = len(names)
            self.done = 0
            self.success = 0
            self.failed = 0
            self.skipped = 0
            self.current = ""
            self.status = "running"
            self.backend = str(options.get("backend", "local") or "local")
            self.logs = []
            self._thread = threading.Thread(target=self._run, args=(list(names), dict(options)), daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self.stop_requested = True
            self.status = "stopping"
            self._log("Stop requested.", "warn")

    def _run(self, names: list[str], options: dict):
        backend = str(options.get("backend", "local") or "local")
        model = options.get("model", "qwen3.5-4b")
        overwrite = normalize_overwrite_mode(options.get("overwrite_mode", "skip"), fallback="skip")
        mode = options.get("mode", "natural")
        prompt = options.get("prompt", "")
        max_tokens = int(options.get("max_tokens", 512))
        thinking = bool(options.get("thinking", False))
        api_base_url = options.get("api_base_url", "")
        api_key = options.get("api_key", "")
        ollama_base_url = options.get("ollama_base_url", "")

        try:
            if backend == "api":
                self._log(f"API backend ready: {model}", "ok")
            elif backend == "ollama":
                self._log(f"Ollama backend ready: {model}", "ok")
            else:
                self.client.load_model(model)
                self._log(f"Model loaded: {model}", "ok")
            for name in names:
                with self._lock:
                    if self.stop_requested:
                        self.status = "stopped"
                        self._log("Batch job stopped.", "warn")
                        break
                    self.current = name

                item = self.workspace.get_item(name)
                has_txt = item["exists"]["txt"]
                if has_txt and overwrite == "skip":
                    with self._lock:
                        self.skipped += 1
                        self.done += 1
                        self._log(f"Skipped {name} (existing TXT).", "warn")
                    continue

                image_paths = collect_item_images(item, control_count=self.workspace.control_count)
                if not image_paths:
                    with self._lock:
                        self.failed += 1
                        self.done += 1
                        self._log(f"Failed {name}: no image available.", "error")
                    continue

                try:
                    request = resolve_caption_request(item["text"], prompt, overwrite_mode=overwrite)
                    result = caption_with_backend(
                        backend=backend,
                        image_paths=image_paths,
                        image_name=name,
                        model=model,
                        mode=mode,
                        prompt=request["prompt"],
                        max_tokens=max_tokens,
                        thinking=thinking,
                        api_base_url=api_base_url,
                        api_key=api_key,
                        ollama_base_url=ollama_base_url,
                        local_client=self.client,
                        api_client=self.api_client,
                        ollama_client=self.ollama_client,
                    )
                    output_text = apply_caption_result(item["text"], result, request["write_mode"])
                    self.workspace.save_text(name, output_text)
                    with self._lock:
                        self.success += 1
                        self.done += 1
                        if request["fallback_to_overwrite"]:
                            self._log(f"Captioned {name} with modify fallback (no existing TXT).", "warn")
                        elif request["used_modify"]:
                            self._log(f"Captioned {name} with modify mode.", "ok")
                        else:
                            self._log(f"Captioned {name}.", "ok")
                except Exception as exc:
                    with self._lock:
                        self.failed += 1
                        self.done += 1
                        self._log(f"Failed {name}: {exc}", "error")

            with self._lock:
                if not self.stop_requested:
                    self.status = "done"
                    self._log(
                        f"Batch done. success={self.success} failed={self.failed} skipped={self.skipped}",
                        "ok",
                    )
        finally:
            with self._lock:
                self.running = False
                self.current = ""
