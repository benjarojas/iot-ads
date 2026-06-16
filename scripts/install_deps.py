"""Install Python dependencies with the right TensorFlow build for this host.

Picks ``requirements-gpu.txt`` (tensorflow[and-cuda]) when an NVIDIA GPU is
detected, otherwise ``requirements-cpu.txt`` (tensorflow-cpu).

GPU detection deliberately requires Linux: native Windows TensorFlow GPU support
was dropped after TF 2.10, so Windows always gets the CPU build (use WSL2 for GPU).

Usage:
    python scripts/install_deps.py            # auto-detect
    python scripts/install_deps.py --cpu      # force CPU build
    python scripts/install_deps.py --gpu      # force GPU build
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def has_nvidia_gpu() -> bool:
    if platform.system() != "Linux":  # TF GPU unsupported on native Windows
        return False
    if not shutil.which("nvidia-smi"):
        return False
    try:
        return subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0
    except Exception:
        return False


def main() -> int:
    args = sys.argv[1:]
    if "--gpu" in args:
        use_gpu = True
    elif "--cpu" in args:
        use_gpu = False
    else:
        use_gpu = has_nvidia_gpu()

    req = ROOT / ("requirements-gpu.txt" if use_gpu else "requirements-cpu.txt")
    print(f"[install_deps] {'GPU' if use_gpu else 'CPU'} build -> installing {req.name}")
    return subprocess.call([sys.executable, "-m", "pip", "install", "-r", str(req)])


if __name__ == "__main__":
    raise SystemExit(main())
