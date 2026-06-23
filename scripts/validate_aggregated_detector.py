#!/usr/bin/env python3
"""Validate / diagnose the AggregatedResidualDetector offline against a labelled capture.

Runs the REAL inference pipeline (MAF -> StandardScaler -> bundle forecast -> EWM)
ONCE, caches the per-window smoothed-residual stream, then scores detectors over the
cache (cheap, no TF) so thresholds/aggregation can be swept instantly.

Reports, on the normal/attack split:
  * OLD  — LogHysteresisDetector on the instantaneous EWM-smoothed residual
  * NEW  — AggregatedResidualDetector (few-second aggregate + dwell), calibrated from
           the bundle's train_residuals
and prints a SKEW DIAGNOSTIC: where the live normal/attack aggregate actually sits
versus the train_residuals-derived trigger. If the live normal floor is above the
trigger, the model's validation residuals were optimistic (train/serve skew) and no
aggregation can help — that's what `--calibrate-from-normal` fixes: it re-derives the
trigger from the live NORMAL aggregates and re-scores, showing the achievable result.

    python scripts/validate_aggregated_detector.py \
        --bundle rpi3b-v2-60m --file exp_context/rpicap_v2.ndjson \
        --attack-start 158 --attack-end 194 --calibrate-from-normal
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.anomaly_detection import AggregatedResidualDetector, LogHysteresisDetector
from app.ml.preprocessing import apply_ewm, apply_moving_average, scale_array
from app.services.model_registry import model_registry

INPUT, FORECAST, STRIDE = 2048, 32, 512
WINDOWS_PER_MESSAGE = INPUT // STRIDE  # 4
RESIDUAL_POINTS_PER_SEC = WINDOWS_PER_MESSAGE * FORECAST  # 128
EPS = 1e-6


def load_frames(path: str) -> list[np.ndarray]:
    frames = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                continue
            obj = json.loads(line)
            if "samples" in obj:
                frames.append(np.asarray(obj["samples"], dtype=np.float32))
    return frames


def build_stream(bundle, frames) -> list[tuple[int, np.ndarray]]:
    """One TF pass: returns [(frame_index, smoothed_residual_window), ...]."""
    ewm = None
    buf: np.ndarray | None = None
    stream = []
    for fi, s in enumerate(frames):
        buf = s.copy() if buf is None else np.concatenate([buf, s])
        if buf.size < INPUT * 2:
            continue
        filt = apply_moving_average(buf)
        for i in range(WINDOWS_PER_MESSAGE):
            off = i * STRIDE
            xi = scale_array(filt[off: off + INPUT], bundle.scaler)
            yt = scale_array(filt[off + INPUT: off + INPUT + FORECAST], bundle.scaler)
            yp = bundle.infer(xi.reshape(1, -1)).numpy()[0]
            sm, ewm = apply_ewm(np.abs(yt - yp), ewm)
            stream.append((fi, sm))
        buf = buf[-INPUT:]
    return stream


def eval_new(det, stream):
    """-> (frame_fired: dict, per_window_agg: list[(fi, agg)])."""
    fired: dict[int, bool] = {}
    aggs = []
    for fi, sm in stream:
        is_anom, agg = det.update(sm)
        fired[fi] = fired.get(fi, False) or is_anom
        aggs.append((fi, agg))
    return fired, aggs


def eval_old(det, stream):
    fired: dict[int, bool] = {}
    for fi, sm in stream:
        is_anom, _, _ = det.detect_window(sm)
        fired[fi] = fired.get(fi, False) or is_anom
    return fired


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--attack-start", type=int, required=True)
    ap.add_argument("--attack-end", type=int, required=True)
    ap.add_argument("--guard", type=int, default=8, help="frames excluded around the attack")
    ap.add_argument("--p-high", type=float, default=99.0)
    ap.add_argument("--p-low", type=float, default=94.0)
    ap.add_argument("--agg-seconds", type=float, default=3.0)
    ap.add_argument("--dwell", type=int, default=2)
    ap.add_argument("--calibrate-from-normal", action="store_true",
                    help="re-derive the trigger from the live NORMAL aggregates and re-score")
    args = ap.parse_args()

    bundle = model_registry.load_bundle(args.bundle)
    bundle.infer(np.zeros((1, INPUT), dtype=np.float32))
    tr = bundle.train_residuals
    agg_window = max(1, int(args.agg_seconds * RESIDUAL_POINTS_PER_SEC))

    frames = load_frames(args.file)
    if not frames:
        print(f"No frames in {args.file}", file=sys.stderr)
        return 1
    stream = build_stream(bundle, frames)

    scored = sorted({fi for fi, _ in stream})
    attack = [i for i in scored if args.attack_start <= i <= args.attack_end]
    normal = [i for i in scored if i < args.attack_start - args.guard
              or i > args.attack_end + args.guard]
    normal_set = set(normal)
    attack_set = set(attack)

    def metrics(fired):
        fp = sum(fired[i] for i in normal)
        tp = sum(fired[i] for i in attack)
        det = [i for i in attack if fired[i]]
        lat = (min(det) - args.attack_start) if det else None
        return (100.0 * fp / max(len(normal), 1), 100.0 * tp / max(len(attack), 1),
                fp, len(normal), tp, len(attack), lat)

    def row(name, fired):
        fpr, rec, fp, nn, tp, na, lat = metrics(fired)
        lat_s = "—" if lat is None else f"{lat}f"
        print(f"{name:22s} {fpr:7.1f}% {rec:7.1f}% {lat_s:>8}   FP {fp}/{nn}  TP {tp}/{na}")

    old = LogHysteresisDetector(train_residuals=tr, p_high=args.p_high, p_low=args.p_low)
    new = AggregatedResidualDetector(tr, args.p_high, args.p_low, agg_window, args.dwell)
    fired_old = eval_old(old, stream)
    fired_new, aggs = eval_new(new, stream)

    print(f"\nbundle={args.bundle}  agg={args.agg_seconds}s ({agg_window} pts)  "
          f"dwell={args.dwell}  p_high/p_low={args.p_high}/{args.p_low}")
    print(f"frames scored={len(scored)}  normal={len(normal)}  attack={len(attack)} "
          f"(attack {args.attack_start}-{args.attack_end})\n")
    print(f"{'detector':22s} {'FP rate':>8} {'recall':>8} {'latency':>8}")
    row("OLD (instantaneous)", fired_old)
    row("NEW (train-resid cal)", fired_new)

    # --- skew diagnostic: where do the live aggregates sit vs the trigger? ---
    norm_agg = np.array([a for fi, a in aggs if fi in normal_set])
    atk_agg = np.array([a for fi, a in aggs if fi in attack_set])
    print(f"\nSKEW DIAGNOSTIC (aggregated residual, units):")
    print(f"  trigger (from train_residuals, p{args.p_high:g}) = {np.exp(new.t_high):.4f}")
    print(f"  live NORMAL aggregate : p50={np.percentile(norm_agg,50):.4f} "
          f"p90={np.percentile(norm_agg,90):.4f} p99={np.percentile(norm_agg,99):.4f}")
    print(f"  live ATTACK aggregate : p50={np.percentile(atk_agg,50):.4f} "
          f"p90={np.percentile(atk_agg,90):.4f} p99={np.percentile(atk_agg,99):.4f}")
    if np.percentile(norm_agg, 50) > np.exp(new.t_high):
        print("  -> live NORMAL floor is ABOVE the trigger: train/serve skew confirmed. "
              "Aggregation cannot fix a mean offset; recalibrate from normal data.")
    sep = np.percentile(norm_agg, 99) < np.percentile(atk_agg, 50)
    print(f"  -> normal p99 {'<' if sep else '>='} attack p50 "
          f"({'separable' if sep else 'OVERLAP'} at the aggregate level)")

    # --- offline test of the fix: calibrate the trigger from live normal aggregates ---
    if args.calibrate_from_normal:
        log_norm = np.log(norm_agg + EPS)
        t_high = float(np.percentile(log_norm, args.p_high))
        t_low = float(np.percentile(log_norm, args.p_low))
        cal = AggregatedResidualDetector(tr, args.p_high, args.p_low, agg_window, args.dwell)
        cal.t_high, cal.t_low = t_high, t_low  # override the train_residuals calibration
        fired_cal, _ = eval_new(cal, stream)
        print(f"\nCALIBRATED-FROM-NORMAL (trigger={np.exp(t_high):.4f}):")
        print(f"{'detector':22s} {'FP rate':>8} {'recall':>8} {'latency':>8}")
        row("NEW (normal-cal)", fired_cal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
