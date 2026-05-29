from __future__ import annotations

import argparse
import os
import platform
import re
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
MIN_VERSION = (3, 10)
MAX_VERSION = (3, 13)
BASE_IMPORTS = ("PIL", "send2trash")


class BootstrapError(RuntimeError):
    pass


def is_windows() -> bool:
    return os.name == "nt"


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if is_windows() else "bin/python")


def check_python_version() -> None:
    version = sys.version_info[:3]
    if version < MIN_VERSION or version >= MAX_VERSION:
        current = ".".join(str(part) for part in version)
        raise BootstrapError(
            f"Python version mismatch: current {current}, required >=3.10 and <3.13. "
            "Python 3.11 is recommended."
        )


def diagnose_failure(text: str) -> str:
    lower = (text or "").lower()
    if "temporary failure" in lower or "name resolution" in lower or "connection" in lower or "timed out" in lower:
        return "Network access failed while installing packages. Check proxy, DNS, firewall, or package index access."
    if "ssl" in lower or "certificate" in lower:
        return "TLS/SSL verification failed. Check system certificates, proxy, or corporate network interception."
    if "no module named venv" in lower or "ensurepip" in lower:
        if platform.system().lower() == "linux":
            return "The Python venv module is missing. Install python3-venv, for example: sudo apt install python3.11-venv"
        return "The Python venv/ensurepip module is missing. Reinstall Python and enable pip."
    if "could not find a version" in lower or "no matching distribution" in lower:
        return "A package wheel was not found for this Python version/platform. Try Python 3.11."
    if "permission denied" in lower or "access is denied" in lower:
        return "Permission denied. Move the project to a writable directory or check antivirus/file locks."
    if "no space left" in lower or "disk full" in lower:
        return "Disk space is insufficient. Free space and retry."
    if "git" in lower and ("not found" in lower or "unable to find" in lower):
        return "Git is required for installing Transformers from GitHub. Install Git and retry."
    return "Package installation failed. See the pip output below."


_PIP_PROGRESS_RE = re.compile(r"progress\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)


def _venv_version_ok() -> bool:
    py = venv_python()
    if not py.exists():
        return False
    result = subprocess.run(
        [
            str(py),
            "-c",
            (
                "import sys; "
                f"raise SystemExit(0 if sys.version_info[:2] >= {MIN_VERSION[:2]!r} and sys.version_info[:2] < {MAX_VERSION[:2]!r} else 1)"
            ),
        ],
        cwd=BASE_DIR,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def _venv_has_imports(modules: tuple[str, ...]) -> bool:
    py = venv_python()
    if not py.exists():
        return False
    module_list = ",".join(repr(name) for name in modules)
    code = (
        "import importlib.util; "
        f"mods=[{module_list}]; "
        "missing=[m for m in mods if importlib.util.find_spec(m) is None]; "
        "raise SystemExit(0 if not missing else 1)"
    )
    result = subprocess.run([str(py), "-c", code], cwd=BASE_DIR, text=True, capture_output=True)
    return result.returncode == 0


def is_base_ready() -> bool:
    return _venv_version_ok() and _venv_has_imports(BASE_IMPORTS)


def is_qwen_ready() -> bool:
    py = venv_python()
    if not is_base_ready() or not py.exists():
        return False
    code = (
        "import importlib.util; "
        "mods=['torch','torchvision','accelerate','huggingface_hub','safetensors']; "
        "missing=[m for m in mods if importlib.util.find_spec(m) is None]; "
        "raise SystemExit(1 if missing else 0)"
    )
    result = subprocess.run([str(py), "-c", code], cwd=BASE_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        return False
    result = subprocess.run(
        [str(py), "-c", "from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration"],
        cwd=BASE_DIR,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def _stream_run(cmd: list[str], *, desc: str) -> str:
    print(f"[env] {desc}")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise BootstrapError(f"Command not found while running {desc}: {cmd[0]}") from exc
    lines: list[str] = []
    last_progress_pct = -5
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        if not line:
            continue
        match = _PIP_PROGRESS_RE.search(line)
        if match:
            current = int(match.group(1))
            total = max(1, int(match.group(2)))
            pct = int((current / total) * 100)
            if pct >= last_progress_pct + 5 or pct >= 100:
                current_mb = current / (1024 ** 2)
                total_mb = total / (1024 ** 2)
                print(f"[env] pip progress {pct}% ({current_mb:.1f}/{total_mb:.1f} MB)", flush=True)
                last_progress_pct = pct
            continue
        print(line, flush=True)
        lines.append(line)
    proc.wait()
    output = "\n".join(lines)
    if proc.returncode == 0:
        return output
    tail = output.strip()[-1600:]
    raise BootstrapError(f"{desc} failed.\n{diagnose_failure(tail)}\n\n{tail}")


def create_venv() -> None:
    if venv_python().exists():
        print(f"[env] Using existing virtual environment: {VENV_DIR}")
        return
    print(f"[env] Creating virtual environment: {VENV_DIR}")
    try:
        import venv
    except Exception as exc:
        raise BootstrapError(
            "Python venv module is missing. On Ubuntu/Debian install python3.11-venv or python3-venv."
        ) from exc
    venv.EnvBuilder(with_pip=True).create(VENV_DIR)


def install_requirements(requirements: Path) -> None:
    py = venv_python()
    if not py.exists():
        raise BootstrapError(f"Virtual environment Python not found: {py}")
    _stream_run([str(py), "-m", "pip", "install", "--progress-bar", "raw", "--upgrade", "pip", "setuptools", "wheel"], desc="Upgrade pip tooling")
    _stream_run(
        [str(py), "-m", "pip", "install", "--progress-bar", "raw", "--disable-pip-version-check", "-r", str(requirements)],
        desc=f"Install {requirements.name}",
    )


def ensure_base() -> None:
    check_python_version()
    create_venv()
    install_requirements(BASE_DIR / "requirements-base.txt")
    print(f"[env] Ready: {venv_python()}")


def ensure_qwen() -> None:
    ensure_base()
    py = venv_python()
    _stream_run(
        [str(py), "-m", "pip", "install", "--progress-bar", "raw", "--disable-pip-version-check", "-r", str(BASE_DIR / "requirements-qwen-cu124.txt")],
        desc="Install Qwen CUDA runtime requirements",
    )
    _stream_run(
        [str(py), "-m", "pip", "install", "--progress-bar", "raw", "--disable-pip-version-check", "--upgrade", "-r", str(BASE_DIR / "requirements-qwen-common.txt")],
        desc="Install Qwen common requirements",
    )
    _stream_run(
        [str(py), "-m", "pip", "install", "--progress-bar", "raw", "--disable-pip-version-check", "--upgrade", "git+https://github.com/huggingface/transformers.git@main"],
        desc="Install latest Transformers for Qwen3.5",
    )
    print(f"[env] Local Qwen ready: {venv_python()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and maintain the local project virtual environment.")
    parser.add_argument("--ensure-base", action="store_true", help="Create .venv and install base dependencies.")
    parser.add_argument("--ensure-qwen", action="store_true", help="Create .venv and install local Qwen dependencies.")
    parser.add_argument("--is-base-ready", action="store_true", help="Exit 0 when the project .venv already has base dependencies.")
    parser.add_argument("--is-qwen-ready", action="store_true", help="Exit 0 when the project .venv already has local Qwen dependencies.")
    parser.add_argument("--print-python", action="store_true", help="Print the .venv Python path.")
    args = parser.parse_args()

    try:
        if args.print_python:
            print(venv_python())
            return 0
        if args.is_base_ready:
            return 0 if is_base_ready() else 1
        if args.is_qwen_ready:
            return 0 if is_qwen_ready() else 1
        if args.ensure_base:
            ensure_base()
            return 0
        if args.ensure_qwen:
            ensure_qwen()
            return 0
        parser.print_help()
        return 0
    except BootstrapError as exc:
        print(f"[env:error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
