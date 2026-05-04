import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler

from app.core.logging_utils import get_logger

logger = get_logger(__name__)

ACTIVE_MODEL_CONFIG_KEY = "active_model"
ACTIVE_MODEL_DEFAULT = "default"

ML_MODELS_ROOT = Path("ml_models")
_REQUIRED_ARTIFACTS = frozenset({"model.keras", "scaler.gz", "train_residuals.npy", "metadata.json"})


@dataclass
class ModelBundle:
    name: str
    predictor: Any          # tf.keras.Model (kept for reference/serialization)
    infer: Any              # tf.function-compiled forward pass — use this for inference
    scaler: StandardScaler
    train_residuals: np.ndarray
    metadata: dict


class ModelRegistry:
    def list_available(self) -> list[str]:
        if not ML_MODELS_ROOT.exists():
            return []
        return [
            d.name
            for d in sorted(ML_MODELS_ROOT.iterdir())
            if d.is_dir() and all((d / f).exists() for f in _REQUIRED_ARTIFACTS)
        ]

    def load_bundle(self, name: str) -> ModelBundle:
        import tensorflow as tf

        bundle_dir = ML_MODELS_ROOT / name
        missing = [f for f in _REQUIRED_ARTIFACTS if not (bundle_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Bundle '{name}' is missing artifacts: {missing}. "
                f"Expected all of {set(_REQUIRED_ARTIFACTS)} inside '{bundle_dir}'."
            )

        logger.info("Loading bundle '%s' from '%s'...", name, bundle_dir)
        predictor = tf.keras.models.load_model(bundle_dir / "model.keras")
        scaler: StandardScaler = joblib.load(bundle_dir / "scaler.gz")
        train_residuals: np.ndarray = np.load(bundle_dir / "train_residuals.npy")
        with open(bundle_dir / "metadata.json") as f:
            metadata = json.load(f)

        infer = tf.function(lambda x: predictor(x, training=False))

        logger.info(
            "Bundle '%s' loaded (train_residuals: %s, scaler: %s).",
            name, train_residuals.shape, type(scaler).__name__,
        )
        return ModelBundle(
            name=name,
            predictor=predictor,
            infer=infer,
            scaler=scaler,
            train_residuals=train_residuals,
            metadata=metadata,
        )


model_registry = ModelRegistry()
