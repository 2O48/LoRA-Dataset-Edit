"""
caption_service.py
本地 Qwen3.5 多模型打标后台服务。
通信协议: stdin/stdout JSON
"""

from __future__ import annotations

import gc
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from caption_image_preprocess import prepare_caption_images
from qwen_models import get_qwen_model_config, list_qwen_model_configs

os.environ["TOKENIZERS_PARALLELISM"] = "false"

BASE_DIR = Path(__file__).parent.resolve()
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

HF_DIR = MODELS_DIR / ".hf-cache"
HF_HUB_DIR = HF_DIR / "hub"
LEGACY_HF_HUB_DIR = MODELS_DIR / "huggingface" / "hub"
HF_DIR.mkdir(exist_ok=True)
HF_HUB_DIR.mkdir(exist_ok=True)
os.environ["HF_HOME"] = str(HF_DIR)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_HUB_DIR)
os.environ["TRANSFORMERS_CACHE"] = str(HF_HUB_DIR)

_qwen_model = None
_qwen_processor = None
_qwen_model_key = ""
_qwen_model_repo = ""

QWEN_SYSTEM_PROMPT = (
    "You are an image captioning assistant. "
    "Always reply with only the final caption in plain English. "
    "No markdown, no bullet points, no analysis, no preamble."
)

QWEN_PROMPTS = {
    "natural": (
        "Write one clean English caption for this image for vision model training. "
        "Focus on subject, material, texture, color, lighting, pose, camera angle, and scene. "
        "Keep it under 60 words."
    ),
    "detail": (
        "Write a detailed English caption for this image for vision model training. "
        "Cover subject, clothing or material, texture, color palette, lighting, composition, "
        "camera angle, background, and mood."
    ),
    "tag": (
        "Describe this image as comma-separated English tags for vision model training. "
        "Use concise tags only. No numbering. No full sentences."
    ),
    "short": (
        "Write a very short English caption for this image for vision model training. "
        "One sentence, under 24 words."
    ),
}


def send(obj: dict):
    try:
        print(json.dumps(obj, ensure_ascii=False), flush=True)
    except Exception:
        print(json.dumps(obj, ensure_ascii=True), flush=True)


def log(message: str, level: str = "info"):
    send({"type": "log", "msg": str(message), "level": level})


def err(message: str):
    send({"type": "error", "msg": str(message)})


def progress(pct: int, message: str = ""):
    send({"type": "progress", "pct": int(pct), "msg": message})


def pip_install(*packages: str, extra_index: str | None = None):
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        "--disable-pip-version-check",
        *packages,
    ]
    if extra_index:
        cmd += ["--index-url", extra_index]
    log(f"安装: {' '.join(packages)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-800:]
        raise RuntimeError(tail or "安装失败")


def _hf_download_with_progress(repo_id: str, model_dir: Path, cache_dir: Path, desc: str, target_gb: float):
    import re

    model_dir.mkdir(parents=True, exist_ok=True)
    log(f"开始下载 {desc}（约 {target_gb:.0f} GB）...")
    log(f"保存位置: {model_dir}")
    progress(15, "正在连接 HuggingFace...")

    dl_script = f"""
import os
os.environ['HF_HOME'] = r'{cache_dir.parent}'
os.environ['HUGGINGFACE_HUB_CACHE'] = r'{cache_dir}'
os.environ['TRANSFORMERS_CACHE'] = r'{cache_dir}'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='{repo_id}',
    cache_dir=r'{cache_dir}',
    local_dir=r'{model_dir}',
    ignore_patterns=['*.pt','flax_model*','tf_model*','rust_model*','onnx*','*.gguf'],
)
print('__DOWNLOAD_DONE__', flush=True)
"""

    proc = subprocess.Popen(
        [sys.executable, "-c", dl_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    done = [False]
    success = [False]

    def read_stderr():
        buffer = ""
        for chunk in iter(lambda: proc.stderr.read(1), ""):
            if chunk in ("\r", "\n"):
                line = buffer.strip()
                buffer = ""
                if not line:
                    continue
                match = re.search(r"(\d+)/(\d+)\s*\[(\d+:\d+)<", line)
                if match:
                    done_n, total_n = int(match.group(1)), int(match.group(2))
                    elapsed = match.group(3)
                    pct_files = done_n / total_n if total_n else 0
                    overall = int(15 + pct_files * 70)
                    msg = f"下载文件 {done_n}/{total_n} 已用时 {elapsed}"
                    progress(min(overall, 88), msg)
                    log(f"  {msg}")
                elif "Downloading" in line or "downloading" in line:
                    size_match = re.search(r"([\d.]+[GMK]?)/([\d.]+[GMK]?)", line)
                    if size_match:
                        log(f"  {line.split(':')[0].strip()}: {size_match.group(1)}/{size_match.group(2)}")
            else:
                buffer += chunk

    def read_stdout():
        for line in proc.stdout:
            line = line.strip()
            if line == "__DOWNLOAD_DONE__":
                success[0] = True
            elif line:
                log(f"  {line}")
        done[0] = True

    t_err = threading.Thread(target=read_stderr, daemon=True)
    t_out = threading.Thread(target=read_stdout, daemon=True)
    t_err.start()
    t_out.start()

    last_size = -1
    while not done[0]:
        time.sleep(4)
        try:
            total_bytes = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
            if total_bytes > 0 and total_bytes != last_size:
                last_size = total_bytes
                log(f"  磁盘已写入: {total_bytes / 1024**3:.2f} GB")
        except Exception:
            pass

    proc.wait()
    t_err.join(timeout=5)
    t_out.join(timeout=5)

    if proc.returncode != 0 or not success[0]:
        remaining = ""
        try:
            remaining = proc.stderr.read() if proc.stderr else ""
        except Exception:
            remaining = ""
        if remaining:
            log(f"下载错误信息: {remaining[-800:]}", "error")
        raise RuntimeError(f"下载失败: {desc}")

    total_bytes = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
    progress(90, f"{desc} 下载完成 {total_bytes / 1024**3:.2f} GB")
    log(f"{desc} 下载完成 OK")


def _cache_has_model(repo_id: str, cache_dir: Path) -> bool:
    slug = repo_id.replace("/", "--")
    snapshots_root = cache_dir / f"models--{slug}" / "snapshots"
    if not snapshots_root.exists():
        return False
    return any((snapshot / "config.json").exists() for snapshot in snapshots_root.iterdir() if snapshot.is_dir())


def _model_dir_has_config(model_dir: Path) -> bool:
    return model_dir.is_dir() and (model_dir / "config.json").exists()


def _release_current_model():
    global _qwen_model, _qwen_processor, _qwen_model_key, _qwen_model_repo

    if _qwen_model is None and _qwen_processor is None:
        return

    log("释放当前本地模型...")
    _qwen_model = None
    _qwen_processor = None
    _qwen_model_key = ""
    _qwen_model_repo = ""
    gc.collect()

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def ensure_deps_qwen():
    try:
        import torch  # noqa: F401
    except Exception:
        log("安装 PyTorch CUDA 12.4...")
        pip_install("torch", "torchvision", extra_index="https://download.pytorch.org/whl/cu124")

    try:
        import PIL  # noqa: F401
    except Exception:
        pip_install("Pillow")

    try:
        import accelerate  # noqa: F401
    except Exception:
        pip_install("--upgrade", "accelerate")

    try:
        import huggingface_hub  # noqa: F401
    except Exception:
        pip_install("--upgrade", "huggingface_hub")

    try:
        from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration  # noqa: F401
    except Exception:
        log("安装/升级 transformers 与依赖（Qwen3.5 需要）...")
        pip_install("--upgrade", "huggingface_hub", "accelerate", "safetensors", "numpy<2", "Pillow")
        pip_install("--upgrade", "git+https://github.com/huggingface/transformers.git@main")
        importlib.invalidate_caches()
        from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration  # noqa: F401


def _resolve_runtime(torch_module):
    if torch_module.cuda.is_available():
        dtype = torch_module.bfloat16 if getattr(torch_module.cuda, "is_bf16_supported", lambda: False)() else torch_module.float16
        return dtype, "auto", "CUDA"
    return torch_module.float32, "cpu", "CPU"


def load_qwen(model_key: str):
    global _qwen_model, _qwen_processor, _qwen_model_key, _qwen_model_repo

    config = get_qwen_model_config(model_key)
    repo_id = config["repo_id"]
    label = config["label"]
    model_dir = Path(config["model_dir"]).expanduser()
    legacy_dir = Path(config["legacy_comfyui_dir"]).expanduser() if config.get("legacy_comfyui_dir") else None
    cache_dir = HF_HUB_DIR

    if _qwen_model is not None and _qwen_model_key == config["key"]:
        log(f"{label} 已加载，直接复用")
        return

    ensure_deps_qwen()

    import torch
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

    if _qwen_model is not None and _qwen_model_key != config["key"]:
        _release_current_model()

    source_path = None
    load_cache_dir = None

    if _model_dir_has_config(model_dir):
        source_path = str(model_dir)
        log(f"{label} 使用项目模型目录: {model_dir}", "ok")
        progress(20, f"{label} 使用项目内模型")
    elif legacy_dir and _model_dir_has_config(legacy_dir):
        source_path = str(legacy_dir)
        log(f"{label} 兼容复用旧目录: {legacy_dir}", "warn")
        progress(20, f"{label} 复用旧目录模型")
    elif _cache_has_model(repo_id, LEGACY_HF_HUB_DIR):
        source_path = repo_id
        load_cache_dir = LEGACY_HF_HUB_DIR
        log(f"{label} 检测到旧缓存，将从 models/huggingface 兼容加载", "warn")
        progress(20, f"{label} 复用旧缓存")
    elif _cache_has_model(repo_id, cache_dir):
        source_path = repo_id
        load_cache_dir = cache_dir
        log(f"{label} 已存在内部缓存，直接加载")
        progress(20, f"{label} 已有内部缓存")
    else:
        _hf_download_with_progress(repo_id, model_dir, cache_dir, label, config["target_gb"])
        source_path = str(model_dir)

    if source_path is None:
        raise RuntimeError(f"Unable to resolve source path for {label}")

    torch_dtype, device_map, runtime_label = _resolve_runtime(torch)
    progress(88, f"加载 {label} Processor...")
    processor_kwargs = {
        "use_fast": False,
        "local_files_only": True,
    }
    if load_cache_dir is not None:
        processor_kwargs["cache_dir"] = str(load_cache_dir)
    _qwen_processor = AutoProcessor.from_pretrained(source_path, **processor_kwargs)

    progress(92, f"加载 {label} 权重...")
    loading_done = [False]

    def heartbeat():
        waited = 0
        while not loading_done[0]:
            time.sleep(5)
            waited += 5
            if not loading_done[0]:
                log(f"  仍在加载中... 已等待 {waited} 秒")

    threading.Thread(target=heartbeat, daemon=True).start()

    model_kwargs = {
        "torch_dtype": torch_dtype,
        "device_map": device_map,
        "local_files_only": True,
    }
    if load_cache_dir is not None:
        model_kwargs["cache_dir"] = str(load_cache_dir)
    _qwen_model = Qwen3_5ForConditionalGeneration.from_pretrained(source_path, **model_kwargs)
    loading_done[0] = True
    _qwen_model.eval()
    _qwen_model_key = config["key"]
    _qwen_model_repo = source_path

    progress(100, f"{label} 加载完成 ({runtime_label})")
    log(f"{label} 加载完成 OK ({runtime_label})", "ok")


def _build_prompt(mode: str, custom_prompt: str) -> str:
    value = (custom_prompt or "").strip()
    if value:
        return value
    return QWEN_PROMPTS.get((mode or "natural").strip().lower(), QWEN_PROMPTS["natural"])


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


def run_qwen(
    image_paths: list[str],
    *,
    mode: str,
    prompt: str,
    image_name: str = "",
    image_file_names: list[str] | None = None,
    max_new_tokens: int,
    thinking: bool,
):
    import re
    import torch

    if _qwen_model is None or _qwen_processor is None:
        raise RuntimeError("Qwen model is not loaded.")
    if not image_paths:
        raise RuntimeError("No images provided for Qwen captioning.")

    prompt_text = _prompt_with_image_name_context(
        _build_prompt(mode, prompt),
        image_name=image_name,
        image_file_names=image_file_names or [Path(path).name for path in image_paths if path],
    )
    full_prompt = f"{QWEN_SYSTEM_PROMPT}\n\n{prompt_text}"
    contents = []
    for image_path in image_paths:
        contents.append({"type": "image", "image": str(image_path)})
    contents.append({"type": "text", "text": full_prompt})
    messages = [
        {
            "role": "user",
            "content": contents,
        }
    ]

    apply_kwargs = {
        "conversation": messages,
        "tokenize": True,
        "add_generation_prompt": True,
        "return_dict": True,
        "return_tensors": "pt",
        "enable_thinking": bool(thinking),
    }
    try:
        inputs = _qwen_processor.apply_chat_template(**apply_kwargs)
    except TypeError:
        apply_kwargs.pop("enable_thinking", None)
        inputs = _qwen_processor.apply_chat_template(**apply_kwargs)

    model_device = next(_qwen_model.parameters()).device
    inputs = {key: value.to(model_device) for key, value in inputs.items()}

    with torch.no_grad():
        output_ids = _qwen_model.generate(
            **inputs,
            max_new_tokens=int(max_new_tokens or 512),
            do_sample=False,
            repetition_penalty=1.08,
        )

    trimmed = [generated[len(source):] for source, generated in zip(inputs["input_ids"], output_ids)]
    text = _qwen_processor.batch_decode(
        trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return " ".join(text.split())


def handle_caption(req: dict):
    raw_paths = req.get("paths") or []
    path = req.get("path", "")
    model = req.get("model", "qwen3.5-4b")
    mode = req.get("mode", "natural")
    req_id = req.get("id", "")
    image_name = str(req.get("image_name", "") or "")
    image_file_names = [str(item) for item in (req.get("image_file_names") or []) if item]

    image_paths = [str(item) for item in raw_paths if item and os.path.exists(str(item))]
    if not image_paths and path and os.path.exists(path):
        image_paths = [path]
    if not image_paths:
        send({"type": "caption_done", "id": req_id, "result": "", "error": "文件不存在或没有可用图像"})
        return

    try:
        if _qwen_model is None or _qwen_model_key != model:
            log(f"加载 {model}...")
            load_qwen(model)

        progress(50, f"{model} 生成描述中...")
        with prepare_caption_images(image_paths) as prepared_paths:
            result = run_qwen(
                prepared_paths,
                mode=mode,
                prompt=req.get("prompt", ""),
                image_name=image_name,
                image_file_names=image_file_names or [Path(path).name for path in image_paths if path],
                max_new_tokens=int(req.get("max_tokens", 512)),
                thinking=bool(req.get("thinking", False)),
            )
        progress(100, "完成")
        send({"type": "caption_done", "id": req_id, "result": result, "error": ""})
    except Exception as exc:
        send(
            {
                "type": "caption_done",
                "id": req_id,
                "result": "",
                "error": str(exc) + "\n" + traceback.format_exc(),
            }
        )


def handle_load(req: dict):
    model = req.get("model", "qwen3.5-4b")
    try:
        progress(0, f"准备加载 {model}...")
        load_qwen(model)
        progress(100, "加载完成")
        send({"type": "load_done", "model": model, "ok": True})
    except Exception as exc:
        err(f"加载失败: {exc}\n{traceback.format_exc()}")
        send({"type": "load_done", "model": model, "ok": False})


def main():
    send({"type": "ready", "supported_models": list_qwen_model_configs()})
    log(f"服务启动，模型目录: {MODELS_DIR}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        cmd = req.get("cmd")
        if cmd == "ping":
            send({"type": "pong"})
        elif cmd == "load":
            handle_load(req)
        elif cmd == "caption":
            handle_caption(req)
        elif cmd == "quit":
            break


if __name__ == "__main__":
    main()
