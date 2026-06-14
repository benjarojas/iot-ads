from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging_utils import get_logger

logger = get_logger(__name__)

# Frame size must match the inference pipeline (2048 samples == 1 message == 1 s).
SAMPLES_PER_FRAME = 2048

# Dragon_Pi CSVs are sampled at ~48828 Hz; the model expects 2048 Hz. We downsample
# with scipy resample_poly(p=512, q=12207) — the exact factors used in training
# (512/12207 == 2048/48828). One downsampled frame (2048 samples) == one real second.
SOURCE_RATE_HZ = 48828
TARGET_RATE_HZ = 2048
RESAMPLE_P = 512
RESAMPLE_Q = 12207

# Suffix used by the capture tooling to pair a dataset with its label summary.
LEGEND_SUFFIX = "_legend.csv"


def data_dir() -> Path:
    return Path(settings.REPLAY_DATA_DIR)


def resolve_dataset(name: str) -> Path:
    """Resolve a dataset filename to a path inside REPLAY_DATA_DIR, guarding
    against path traversal. Raises FileNotFoundError / ValueError on problems."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Invalid dataset name: {name!r}")
    root = data_dir().resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise ValueError(f"Dataset name escapes data directory: {name!r}")
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {name!r}")
    return path


def _parse_legend(legend_path: Path) -> dict:
    """Aggregate a *_legend.csv into a compact label summary."""
    total_samples = 0
    anomaly_samples = 0
    anomaly_types: list[str] = []
    try:
        with legend_path.open("r", newline="") as f:
            for row in csv.DictReader(f):
                n = int(float(row.get("number_of_samples") or 0))
                total_samples += n
                anom = int(float(row.get("total_anom") or 0))
                anomaly_samples += anom
                atype = (row.get("anno_type") or "").strip()
                if atype and atype.lower() != "normal" and atype not in anomaly_types:
                    anomaly_types.append(atype)
    except Exception:
        logger.exception("Failed to parse legend %s", legend_path)
        return {}
    return {
        "anomaly_samples": anomaly_samples,
        "anomaly_types": anomaly_types,
        "has_anomalies": anomaly_samples > 0 or bool(anomaly_types),
    }


def _estimate_frames(path: Path) -> Optional[int]:
    """Estimate the number of 2048-sample (1-second) frames after downsampling.

    File-size / average-line-length sampled mid-file (the legend's sample counts
    only cover anomaly segments, not the whole file). A CSV's source rows are
    downsampled 48828→2048 Hz, so frames ≈ source_rows / SOURCE_RATE_HZ (one frame
    per real second). An NDJSON is already 2048 Hz with one batch per line.
    """
    size = path.stat().st_size
    if size == 0:
        return None
    sample_bytes = sample_lines = 0
    try:
        with path.open("rb") as f:
            f.seek(size // 2)
            f.readline()  # discard partial line
            for _ in range(2000):
                line = f.readline()
                if not line:
                    break
                sample_bytes += len(line)
                sample_lines += 1
    except OSError:
        return None
    if sample_lines == 0:
        return None
    est_lines = size / (sample_bytes / sample_lines)
    if path.suffix.lower() == ".ndjson":
        return max(1, int(est_lines))
    return max(1, int(est_lines / SOURCE_RATE_HZ))


def _describe(path: Path) -> dict:
    name = path.name
    suffix = path.suffix.lower()
    fmt = "csv" if suffix == ".csv" else ("ndjson" if suffix == ".ndjson" else suffix.lstrip("."))
    info: dict = {
        "name": name,
        "size_bytes": path.stat().st_size,
        "format": fmt,
        "has_labels": fmt == "csv",  # only the supervised CSVs carry per-sample labels
        "total_samples": None,
        "total_frames": _estimate_frames(path),
        "anomaly_types": [],
        "has_anomalies": False,
    }
    if fmt == "csv":
        legend = path.with_name(f"{path.stem}{LEGEND_SUFFIX}")
        if legend.is_file():
            summary = _parse_legend(legend)
            info["anomaly_types"] = summary.get("anomaly_types", [])
            info["has_anomalies"] = summary.get("has_anomalies", False)
    return info


def list_datasets() -> list[dict]:
    root = data_dir()
    if not root.exists():
        logger.warning("Replay data dir '%s' does not exist.", root)
        return []
    out: list[dict] = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if path.name.endswith(LEGEND_SUFFIX):
            continue  # legend files are metadata, not standalone datasets
        if path.suffix.lower() not in (".csv", ".ndjson"):
            continue
        out.append(_describe(path))
    return out


def estimate_total_frames(name: str) -> Optional[int]:
    """Best-effort total frame count for the progress bar (see _estimate_frames)."""
    try:
        return _estimate_frames(resolve_dataset(name))
    except (FileNotFoundError, ValueError):
        return None
