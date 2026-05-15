from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
MIN_VERSION = (3, 10)
MAX_VERSION = (3, 13)


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


def run(cmd: list[str], *, desc: str) -> None:
    print(f"[env] {desc}")
    try:
        result = subprocess.run(cmd, cwd=BASE_DIR, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise BootstrapError(f"Command not found while running {desc}: {cmd[0]}") from exc
    if result.returncode == 0:
        return
    tail = (result.stderr or result.stdout or "").strip()[-1600:]
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
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], desc="Upgrade pip tooling")
    run(
        [str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
        desc=f"Install {requirements.name}",
    )


def ensure_base() -> None:
    check_python_version()
    create_venv()
    install_requirements(BASE_DIR / "requirements-base.txt")
    print(f"[env] Ready: {venv_python()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and maintain the local project virtual environment.")
    parser.add_argument("--ensure-base", action="store_true", help="Create .venv and install base dependencies.")
    parser.add_argument("--print-python", action="store_true", help="Print the .venv Python path.")
    args = parser.parse_args()

    try:
        if args.print_python:
            print(venv_python())
            return 0
        if args.ensure_base:
            ensure_base()
            return 0
        parser.print_help()
        return 0
    except BootstrapError as exc:
        print(f"[env:error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
