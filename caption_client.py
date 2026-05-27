from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"


def project_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def running_in_project_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == project_python().resolve()
    except Exception:
        return False


def diagnose_pip_failure(text: str) -> str:
    lower = (text or "").lower()
    if "no module named venv" in lower or "ensurepip" in lower:
        if sys.platform.startswith("linux"):
            return "当前 Python 缺少 venv/ensurepip。Ubuntu/Debian 可安装 python3.11-venv 或 python3-venv 后重试。"
        return "当前 Python 缺少 venv/ensurepip。请重新安装 Python，并勾选 pip/venv 组件。"
    if "could not find a version" in lower or "no matching distribution" in lower:
        return "没有找到适配当前 Python/系统的安装包。建议使用 Python 3.11。"
    if "temporary failure" in lower or "name resolution" in lower or "connection" in lower or "timed out" in lower:
        return "网络连接失败。请检查代理、DNS、防火墙或 pip 源访问。"
    if "ssl" in lower or "certificate" in lower:
        return "SSL/证书校验失败。请检查系统证书、代理或公司网络拦截。"
    if "permission denied" in lower or "access is denied" in lower:
        return "权限不足或文件被占用。请确认项目目录可写，或关闭占用 .venv 的进程。"
    if "no space left" in lower or "disk full" in lower:
        return "磁盘空间不足。请释放空间后重试。"
    if "git" in lower and ("not found" in lower or "unable to find" in lower):
        return "安装 Transformers main 分支需要 Git。请安装 Git 后重试。"
    return "pip 安装失败，请查看下方错误输出。"


def diagnose_python_start_failure(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "项目 .venv 的 Python 不存在。请先通过 ./start.sh 或 run.bat 启动，或重新点击安装让系统创建 .venv。"
    if isinstance(exc, PermissionError):
        return "权限不足或文件被占用。请确认项目目录可写，并关闭正在占用 .venv 的进程。"
    return str(exc) or "启动 Python 进程失败。"


class CaptionServiceClient:
    def __init__(self, service_path: Optional[Path] = None):
        self.service_path = service_path or (BASE_DIR / "caption_service.py")
        self.proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._reader_thread: Optional[threading.Thread] = None
        self._pending: dict[str, queue.Queue] = {}
        self._req_id = 0
        self._load_waiter: Optional[queue.Queue] = None
        self._logs: deque[dict] = deque(maxlen=600)
        self.ready = False
        self.progress_pct = 0
        self.progress_msg = ""
        self.status = "stopped"
        self.loaded_models: set[str] = set()
        self.supported_models: list[dict] = []

    def _append_log(self, message: str, level: str = "info"):
        ts = time.strftime("%H:%M:%S")
        self._logs.append({"ts": ts, "level": level, "message": message})
        print(f"[{ts}] [local] [{level}] {message}", flush=True)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "ready": self.ready,
                "status": self.status,
                "progress_pct": self.progress_pct,
                "progress_msg": self.progress_msg,
                "loaded_models": sorted(self.loaded_models),
                "supported_models": list(self.supported_models),
                "logs": list(self._logs),
                "running": self.proc is not None and self.proc.poll() is None,
            }

    def start(self):
        with self._lock:
            if self.proc and self.proc.poll() is None:
                return
            if not self.service_path.exists():
                raise FileNotFoundError(f"caption_service.py not found: {self.service_path}")

            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            child_python = project_python() if project_python().exists() else Path(sys.executable)
            self.proc = subprocess.Popen(
                [str(child_python), str(self.service_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
                start_new_session=sys.platform != "win32",
            )
            self.ready = False
            self.status = "starting"
            self.progress_pct = 0
            self.progress_msg = "starting"
            self.loaded_models.clear()
            self._append_log(f"Starting caption service: {self.service_path}")
            self._append_log(f"Caption service Python: {child_python}")
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()

    def stop(self):
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                return
            try:
                self._send({"cmd": "quit"})
            except Exception:
                pass
            try:
                self._terminate_process_tree()
            except Exception:
                pass
            self.ready = False
            self.status = "stopped"

    def _terminate_process_tree(self):
        if not self.proc or self.proc.poll() is not None:
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            self.proc.terminate()

    def cancel_load(self) -> bool:
        with self._lock:
            if self._load_waiter is None:
                return False
            waiter = self._load_waiter
            self._append_log("model loading cancelled", "warn")
            try:
                self._terminate_process_tree()
            except Exception:
                pass
            self.ready = False
            self.status = "stopped"
            self.progress_pct = 0
            self.progress_msg = "model loading cancelled"
            self.loaded_models.clear()
            try:
                waiter.put_nowait({"type": "load_done", "model": "", "ok": False, "cancelled": True, "error": "model loading cancelled"})
            except queue.Full:
                pass
            return True

    def ensure_started(self, timeout: float = 10.0):
        self.start()
        start = time.time()
        while time.time() - start < timeout:
            if self.ready:
                return
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError("caption service exited unexpectedly")
            time.sleep(0.1)
        raise TimeoutError("caption service did not become ready in time")

    def _send(self, payload: dict):
        if not self.proc or self.proc.poll() is not None or not self.proc.stdin:
            raise RuntimeError("caption service is not running")
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _reader_loop(self):
        if not self.proc or not self.proc.stdout:
            return
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except Exception:
                with self._lock:
                    self._append_log(line, "info")
                continue
            self._handle_message(message)
        with self._lock:
            self.ready = False
            self.status = "stopped"
            self.loaded_models.clear()
            self._append_log("caption service exited", "warn")

    def _handle_message(self, message: dict):
        msg_type = message.get("type")
        with self._lock:
            if msg_type == "ready":
                self.ready = True
                self.status = "ready"
                self.supported_models = list(message.get("supported_models") or [])
                self._append_log("caption service ready", "ok")
                return
            if msg_type == "log":
                self._append_log(message.get("msg", ""), message.get("level", "info"))
                return
            if msg_type == "error":
                self.status = "error"
                self._append_log(message.get("msg", ""), "error")
                return
            if msg_type == "progress":
                self.progress_pct = int(message.get("pct", 0))
                self.progress_msg = message.get("msg", "")
                self.status = "busy"
                if self.progress_msg:
                    self._append_log(f"{self.progress_pct}% {self.progress_msg}", "info")
                return
            if msg_type == "load_done":
                model = message.get("model", "")
                ok = bool(message.get("ok"))
                if ok and model:
                    self.loaded_models = {model}
                    self.status = "ready"
                    self.progress_pct = 100
                    self.progress_msg = f"{model} loaded"
                    self._append_log(f"{model} loaded", "ok")
                else:
                    self.status = "error"
                    self._append_log(f"{model} failed to load", "error")
                if self._load_waiter is not None:
                    self._load_waiter.put(message)
                return
            if msg_type == "caption_done":
                req_id = message.get("id", "")
                waiter = self._pending.pop(req_id, None)
                if waiter is not None:
                    waiter.put(message)
                return

    def load_model(self, model: str, timeout: float = 900.0) -> dict:
        self.ensure_started()
        with self._lock:
            if self.loaded_models == {model}:
                self.status = "ready"
                return {"type": "load_done", "model": model, "ok": True, "cached": True}
            self._load_waiter = queue.Queue(maxsize=1)
            self.status = "loading"
        self._send({"cmd": "load", "model": model})
        try:
            result = self._load_waiter.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError(f"loading model timed out: {model}") from exc
        finally:
            with self._lock:
                self._load_waiter = None
        if result.get("cancelled"):
            raise RuntimeError("model loading cancelled")
        if not result.get("ok"):
            raise RuntimeError(f"failed to load model: {model}")
        return result

    def caption(
        self,
        *,
        image_path: str = "",
        image_paths: Optional[list[str]] = None,
        image_name: str = "",
        image_file_names: Optional[list[str]] = None,
        model: str,
        mode: str = "natural",
        prompt: str = "",
        max_tokens: int = 512,
        thinking: bool = False,
        timeout: float = 1200.0,
    ) -> str:
        self.ensure_started()
        with self._lock:
            self._req_id += 1
            req_id = str(self._req_id)
            waiter = queue.Queue(maxsize=1)
            self._pending[req_id] = waiter
            self.status = "captioning"

        self._send(
            {
                "cmd": "caption",
                "id": req_id,
                "path": image_path,
                "paths": list(image_paths or ([image_path] if image_path else [])),
                "image_name": image_name,
                "image_file_names": list(image_file_names or []),
                "model": model,
                "mode": mode,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "thinking": thinking,
            }
        )

        try:
            result = waiter.get(timeout=timeout)
        except queue.Empty as exc:
            with self._lock:
                self._pending.pop(req_id, None)
            raise TimeoutError("caption request timed out") from exc

        error_message = result.get("error", "")
        if error_message:
            raise RuntimeError(error_message)
        with self._lock:
            self.status = "ready"
        return result.get("result", "")


class DependencyInstaller:
    def __init__(self):
        self._lock = threading.RLock()
        self.running = False
        self.logs: deque[dict] = deque(maxlen=400)
        self.status = "idle"
        self.progress_pct = 0
        self.target_python = str(project_python())

    def _append(self, message: str, level: str = "info"):
        ts = time.strftime("%H:%M:%S")
        self.logs.append({"ts": ts, "level": level, "message": message})
        print(f"[{ts}] [install] [{level}] {message}", flush=True)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "status": self.status,
                "progress_pct": self.progress_pct,
                "target_python": self.target_python,
                "logs": list(self.logs),
            }

    def start(self):
        with self._lock:
            if self.running:
                return False
            self.running = True
            self.status = "running"
            self.progress_pct = 0
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _finish(self, status: str, progress_pct: int):
        with self._lock:
            self.running = False
            self.status = status
            self.progress_pct = progress_pct

    def _run_step(self, name: str, cmd: list[str], progress_pct: int) -> bool:
        self._append(f"Installing {name}...", "warn")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True, creationflags=creationflags)
        except Exception as exc:
            self._append(f"{name} failed: {diagnose_python_start_failure(exc)}", "error")
            return False
        if result.returncode == 0:
            with self._lock:
                self.progress_pct = progress_pct
            self._append(f"{name} OK", "ok")
            return True
        tail = (result.stderr or result.stdout or "").strip()[-1200:]
        self._append(f"{name} failed: {diagnose_pip_failure(tail)} {tail}", "error")
        return False

    def _run(self):
        bootstrap_py = Path(sys.executable)
        version = sys.version_info
        if version < (3, 10) or version >= (3, 13):
            self._append(
                f"Python 版本不匹配：{version.major}.{version.minor}.{version.micro}，需要 >=3.10 且 <3.13，推荐 3.11。",
                "error",
            )
            self._finish("failed", 0)
            return

        venv_py = project_python()
        self.target_python = str(venv_py)
        self._append(f"准备项目虚拟环境: {VENV_DIR}", "info")
        self._append(f"安装目标 Python: {venv_py}", "info")
        if not running_in_project_venv():
            self._append("当前服务不在项目 .venv 中，安装仍会强制写入项目 .venv，不会改动 Conda/系统环境。", "warn")

        if not self._run_step("project .venv and base requirements", [str(bootstrap_py), str(BASE_DIR / "bootstrap_env.py"), "--ensure-base"], 20):
            self._finish("failed", self.progress_pct)
            return
        if not venv_py.exists():
            self._append(f"项目 .venv Python 不存在: {venv_py}", "error")
            self._finish("failed", self.progress_pct)
            return

        steps = [
            ("PyTorch CUDA 12.4", [str(venv_py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(BASE_DIR / "requirements-qwen-cu124.txt")]),
            ("huggingface_hub / accelerate / pillow / safetensors", [str(venv_py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--upgrade", "-r", str(BASE_DIR / "requirements-qwen-common.txt")]),
            ("transformers latest for Qwen3.5", [str(venv_py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "git+https://github.com/huggingface/transformers.git@main"]),
        ]

        ok = True
        for index, (name, cmd) in enumerate(steps, start=1):
            progress_pct = 20 + int(index / len(steps) * 75)
            if not self._run_step(name, cmd, progress_pct):
                ok = False

        if ok:
            self._append("Qwen 依赖已安装到项目 .venv。", "ok")
        self._finish("done" if ok else "failed", 100 if ok else self.progress_pct)
