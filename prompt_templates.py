from __future__ import annotations

import json
import time
from pathlib import Path
from threading import RLock

DEFAULT_TEMPLATES = [
    {
        "id": "cn-min-change",
        "name": "中文·极简变化",
        "content": "仅描述控制图1到结果图的变化，极简描述，中文描述。",
        "updated_at": "",
    },
    {
        "id": "cn-multi-change",
        "name": "中文·多图差异",
        "content": "结合所有控制图与结果图，仅描述控制图到结果图的主要变化，忽略未变化内容，极简描述，中文输出。",
        "updated_at": "",
    },
    {
        "id": "en-lora-short",
        "name": "English·LoRA Short",
        "content": "Write one short English caption for the difference from the control images to the result image. Focus only on visible changes.",
        "updated_at": "",
    },
]


class PromptTemplateStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()

    def load(self) -> list[dict]:
        with self._lock:
            if not self.path.exists():
                return list(DEFAULT_TEMPLATES)
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return list(DEFAULT_TEMPLATES)
            if not isinstance(data, list):
                return list(DEFAULT_TEMPLATES)
            items = [item for item in data if isinstance(item, dict) and item.get("name") and item.get("content")]
            return items or list(DEFAULT_TEMPLATES)

    def save_template(self, *, name: str, content: str) -> list[dict]:
        cleaned_name = (name or "").strip()
        cleaned_content = (content or "").strip()
        if not cleaned_name:
            raise ValueError("Template name is required.")
        if not cleaned_content:
            raise ValueError("Template content is required.")

        with self._lock:
            items = self.load()
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            template_id = self._slugify(cleaned_name)
            existing = next((item for item in items if item.get("id") == template_id), None)
            if existing is None:
                items.append(
                    {
                        "id": template_id,
                        "name": cleaned_name,
                        "content": cleaned_content,
                        "updated_at": now,
                    }
                )
            else:
                existing["name"] = cleaned_name
                existing["content"] = cleaned_content
                existing["updated_at"] = now
            self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            return items

    def delete_template(self, template_id: str) -> list[dict]:
        target_id = (template_id or "").strip()
        if not target_id:
            raise ValueError("Template id is required.")

        with self._lock:
            items = [item for item in self.load() if item.get("id") != target_id]
            self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            return items

    def _slugify(self, text: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug or "template"
