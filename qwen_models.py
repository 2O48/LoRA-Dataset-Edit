from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
PROJECT_MODELS_DIR = BASE_DIR / "models"
LEGACY_COMFYUI_LLM_DIR = Path.home() / "ComfyUI" / "models" / "LLM"
LEGACY_HF_HUB_DIR = PROJECT_MODELS_DIR / "huggingface" / "hub"

PROJECT_MODELS_DIR.mkdir(exist_ok=True)

QWEN_MODELS = [
    {
        "key": "qwen3.5-0.8b",
        "label": "Qwen3.5-0.8B",
        "repo_id": "Qwen/Qwen3.5-0.8B",
        "size_note": "轻量试跑",
        "thinking_default": False,
        "target_gb": 3.0,
    },
    {
        "key": "qwen3.5-2b",
        "label": "Qwen3.5-2B",
        "repo_id": "Qwen/Qwen3.5-2B",
        "size_note": "中小规模",
        "thinking_default": False,
        "target_gb": 5.0,
    },
    {
        "key": "qwen3.5-4b",
        "label": "Qwen3.5-4B",
        "repo_id": "Qwen/Qwen3.5-4B",
        "size_note": "默认推荐",
        "thinking_default": True,
        "target_gb": 8.0,
    },
    {
        "key": "qwen3.5-9b",
        "label": "Qwen3.5-9B",
        "repo_id": "Qwen/Qwen3.5-9B",
        "size_note": "高质量",
        "thinking_default": True,
        "target_gb": 18.0,
    },
    {
        "key": "qwen3.5-27b",
        "label": "Qwen3.5-27B",
        "repo_id": "Qwen/Qwen3.5-27B",
        "size_note": "大模型",
        "thinking_default": True,
        "target_gb": 54.0,
    },
]

QWEN_MODEL_MAP = {item["key"]: item for item in QWEN_MODELS}


def _has_model_files(path: Path) -> bool:
    return path.is_dir() and (path / "config.json").exists()


def _legacy_cache_has_model(repo_id: str) -> bool:
    slug = repo_id.replace("/", "--")
    snapshots_root = LEGACY_HF_HUB_DIR / f"models--{slug}" / "snapshots"
    if not snapshots_root.exists():
        return False
    return any((snapshot / "config.json").exists() for snapshot in snapshots_root.iterdir() if snapshot.is_dir())


def _build_model_config(config: dict) -> dict:
    result = dict(config)
    label = result["label"]
    repo_id = result["repo_id"]
    model_dir = PROJECT_MODELS_DIR / label
    legacy_dir = LEGACY_COMFYUI_LLM_DIR / label

    result["model_dir"] = str(model_dir)
    result["model_dir_rel"] = f"models/{label}"
    result["project_local_available"] = _has_model_files(model_dir)
    result["legacy_comfyui_dir"] = str(legacy_dir) if _has_model_files(legacy_dir) else ""
    result["legacy_hf_cache_available"] = _legacy_cache_has_model(repo_id)
    return result


def list_qwen_model_configs() -> list[dict]:
    return [_build_model_config(item) for item in QWEN_MODELS]


def get_qwen_model_config(model_key: str | None) -> dict:
    key = (model_key or "").strip().lower()
    if not key:
        key = "qwen3.5-4b"
    config = QWEN_MODEL_MAP.get(key)
    if config is None:
        supported = ", ".join(item["key"] for item in QWEN_MODELS)
        raise KeyError(f"Unsupported Qwen model: {model_key}. Supported: {supported}")
    return _build_model_config(config)
