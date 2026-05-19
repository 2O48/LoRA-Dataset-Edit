from __future__ import annotations

import base64
import json
import mimetypes
import tempfile
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from threading import RLock

from PIL import Image

from caption_image_preprocess import prepare_caption_images

DEFAULT_PROMPTS = {
    "natural": (
        "Write one clean English caption for this image for Stable Diffusion LoRA training. "
        "Focus on subject, material, texture, color, lighting, pose, camera angle, and scene. "
        "Keep it under 60 words."
    ),
    "detail": (
        "Write a detailed English caption for this image for Stable Diffusion LoRA training. "
        "Cover subject, clothing or material, texture, color palette, lighting, composition, "
        "camera angle, background, and mood."
    ),
    "tag": (
        "Describe this image as comma-separated English tags for Stable Diffusion LoRA training. "
        "Use concise tags only. No numbering. No full sentences."
    ),
    "short": (
        "Write a very short English caption for this image for Stable Diffusion LoRA training. "
        "One sentence, under 24 words."
    ),
}


def _normalize_endpoint(base_url: str) -> str:
    value = (base_url or "").strip()
    if not value:
        raise RuntimeError("API Base URL is required.")

    value = value.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return f"{value}/chat/completions"
    return f"{value}/chat/completions"


def _normalize_models_endpoint(base_url: str) -> str:
    value = (base_url or "").strip()
    if not value:
        raise RuntimeError("API Base URL is required.")

    value = value.rstrip("/")
    if value.endswith("/models"):
        return value
    if value.endswith("/chat/completions"):
        value = value[: -len("/chat/completions")]
    if value.endswith("/v1"):
        return f"{value}/models"
    return f"{value}/models"


def _prompt_for_mode(mode: str, prompt: str) -> str:
    custom = (prompt or "").strip()
    if custom:
        return custom
    return DEFAULT_PROMPTS.get(mode or "natural", DEFAULT_PROMPTS["natural"])


def _image_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"].strip()
        if isinstance(content.get("content"), str):
            return content["content"].strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _content_to_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _extract_response_text(payload: dict) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] or {}
        message = first.get("message") or {}
        text = _content_to_text(message.get("content"))
        if text:
            return text

    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            text = _content_to_text((item or {}).get("content"))
            if text:
                return text
    return ""


def _compact_text(text: str) -> str:
    return " ".join((text or "").split())


def _prompt_with_image_name_context(prompt: str, *, image_name: str = "", image_file_names: list[str] | None = None) -> str:
    lines: list[str] = []
    clean_name = (image_name or "").strip()
    if clean_name:
        lines.append(f"Dataset item name: {clean_name}")
    clean_files = [str(name).strip() for name in (image_file_names or []) if str(name).strip()]
    if clean_files:
        label = "Image file names" if len(clean_files) > 1 else "Image file name"
        lines.append(f"{label}: {', '.join(clean_files)}")
    if not lines:
        return prompt
    return f"{prompt.rstrip()}\n\nFile name context:\n" + "\n".join(lines)


def _extract_model_ids(payload) -> list[str]:
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            raw_items = payload["data"]
        elif isinstance(payload.get("models"), list):
            raw_items = payload["models"]
        else:
            raw_items = []
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = []

    models: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or item.get("model") or "").strip()
        else:
            model_id = ""
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append(model_id)
    return sorted(models, key=lambda value: value.lower())


class APICaptionClient:
    def __init__(self):
        self._lock = RLock()
        self._logs: deque[dict] = deque(maxlen=300)
        self.status = "idle"
        self.progress_msg = ""
        self.last_model = ""
        self.last_endpoint = ""
        self.last_backend = "OpenAI Compatible"

    def _append_log(self, message: str, level: str = "info"):
        ts = time.strftime("%H:%M:%S")
        self._logs.append(
            {
                "ts": ts,
                "level": level,
                "message": message,
            }
        )
        print(f"[{ts}] [api] [{level}] {message}", flush=True)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "ready": self.status not in {"error"},
                "status": self.status,
                "progress_msg": self.progress_msg,
                "last_model": self.last_model,
                "last_endpoint": self.last_endpoint,
                "last_backend": self.last_backend,
                "logs": list(self._logs),
            }

    def caption(
        self,
        *,
        image_path: str,
        image_paths: list[str] | None = None,
        image_name: str = "",
        image_file_names: list[str] | None = None,
        api_base_url: str,
        api_key: str,
        model: str,
        mode: str = "natural",
        prompt: str = "",
        max_tokens: int = 512,
        timeout: float = 180.0,
    ) -> str:
        if not (model or "").strip():
            raise RuntimeError("API model is required.")

        endpoint = _normalize_endpoint(api_base_url)
        all_image_paths = list(image_paths or ([image_path] if image_path else []))
        if not all_image_paths:
            raise RuntimeError("At least one image is required.")
        resolved_prompt = _prompt_with_image_name_context(
            _prompt_for_mode(mode, prompt),
            image_name=image_name,
            image_file_names=image_file_names or [Path(path).name for path in all_image_paths if path],
        )
        user_content = [{"type": "text", "text": resolved_prompt}]
        with prepare_caption_images(all_image_paths) as prepared_paths:
            for path in prepared_paths:
                user_content.append({"type": "image_url", "image_url": {"url": _image_data_url(path)}})

            payload = {
                "model": model.strip(),
                "messages": [
                    {
                        "role": "system",
                        "content": "You generate precise image captions for LoRA dataset annotation.",
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                "max_tokens": int(max_tokens or 512),
            }

            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "LoRADataEdit/1.0",
            }
            if (api_key or "").strip():
                headers["Authorization"] = f"Bearer {api_key.strip()}"

            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with self._lock:
                self.status = "requesting"
                self.progress_msg = f"Calling API model {model.strip()}"
                self.last_model = model.strip()
                self.last_endpoint = endpoint
                self._append_log(f"Calling API backend {endpoint}", "warn")

            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                message = body.strip() or str(exc)
                with self._lock:
                    self.status = "error"
                    self.progress_msg = "API request failed"
                    self._append_log(f"API request failed: {message[-500:]}", "error")
                raise RuntimeError(message[-500:] or "API request failed.") from exc
            except Exception as exc:
                with self._lock:
                    self.status = "error"
                    self.progress_msg = "API request failed"
                    self._append_log(f"API request failed: {exc}", "error")
                raise RuntimeError(f"API request failed: {exc}") from exc

            try:
                data = json.loads(raw)
            except Exception as exc:
                with self._lock:
                    self.status = "error"
                    self.progress_msg = "Invalid API response"
                    self._append_log("API returned invalid JSON.", "error")
                raise RuntimeError("API returned invalid JSON.") from exc

            text = _compact_text(_extract_response_text(data))
            if not text:
                with self._lock:
                    self.status = "error"
                    self.progress_msg = "Empty API response"
                    self._append_log("API returned no caption text.", "error")
                raise RuntimeError("API returned no caption text.")

            with self._lock:
                self.status = "ready"
                self.progress_msg = f"API caption ready: {self.last_model}"
                self._append_log(f"API caption ready: {self.last_model}", "ok")
            return text

    def list_models(
        self,
        *,
        api_base_url: str,
        api_key: str,
        timeout: float = 45.0,
    ) -> list[str]:
        endpoint = _normalize_models_endpoint(api_base_url)
        headers = {
            "Accept": "application/json",
            "User-Agent": "LoRADataEdit/1.0",
        }
        if (api_key or "").strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        request = urllib.request.Request(endpoint, headers=headers, method="GET")
        with self._lock:
            self.status = "requesting"
            self.progress_msg = "Reading API model list"
            self.last_endpoint = endpoint
            self._append_log(f"Reading API models from {endpoint}", "warn")

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            message = body.strip() or str(exc)
            with self._lock:
                self.status = "error"
                self.progress_msg = "API model list failed"
                self._append_log(f"API model list failed: {message[-500:]}", "error")
            raise RuntimeError(message[-500:] or "API model list failed.") from exc
        except Exception as exc:
            with self._lock:
                self.status = "error"
                self.progress_msg = "API model list failed"
                self._append_log(f"API model list failed: {exc}", "error")
            raise RuntimeError(f"API model list failed: {exc}") from exc

        try:
            data = json.loads(raw)
        except Exception as exc:
            with self._lock:
                self.status = "error"
                self.progress_msg = "Invalid API model response"
                self._append_log("API model list returned invalid JSON.", "error")
            raise RuntimeError("API model list returned invalid JSON.") from exc

        models = _extract_model_ids(data)
        with self._lock:
            self.status = "ready"
            self.progress_msg = f"API models ready: {len(models)}"
            self._append_log(f"API models ready: {len(models)}", "ok" if models else "warn")
        return models

    def validate(
        self,
        *,
        api_base_url: str,
        api_key: str,
        model: str,
        mode: str = "natural",
        prompt: str = "",
        max_tokens: int = 128,
    ) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
        try:
            Image.new("RGB", (96, 96), (214, 136, 78)).save(image_path)
            result = self.caption(
                image_path=image_path,
                api_base_url=api_base_url,
                api_key=api_key,
                model=model,
                mode=mode,
                prompt=prompt or "Describe this simple orange square image in one short sentence.",
                max_tokens=max_tokens,
            )
            return {
                "ok": True,
                "result": result,
                "backend": self.last_backend,
                "model": self.last_model,
                "endpoint": self.last_endpoint,
            }
        finally:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
