import os
import json
import logging
from datetime import datetime, timezone
import joblib

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
METADATA_FILE = os.path.join(MODELS_DIR, "model_metadata.json")


def ensure_models_dir():
    os.makedirs(MODELS_DIR, exist_ok=True)


def load_model_metadata() -> dict:
    ensure_models_dir()
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading model metadata: {e}")
    return {
        "version": "1.0.0",
        "last_trained_at": None,
        "models": {}
    }


def save_model_metadata(metadata: dict):
    ensure_models_dir()
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)


def save_model_bundle(
    pipeline_name: str,
    model_obj,
    metrics: dict,
    features: list,
    version: str = "1.0.0"
) -> bool:
    """
    Saves a trained model to saved_models/{pipeline_name}.joblib
    and updates model_metadata.json with regression-guard check.
    """
    ensure_models_dir()
    model_path = os.path.join(MODELS_DIR, f"{pipeline_name}.joblib")
    
    # Save the model artifact
    joblib.dump({
        "model": model_obj,
        "features": features,
        "metrics": metrics,
        "version": version,
        "saved_at": datetime.now(timezone.utc).isoformat()
    }, model_path)

    # Update metadata
    metadata = load_model_metadata()
    metadata["last_trained_at"] = datetime.now(timezone.utc).isoformat()
    metadata["models"][pipeline_name] = {
        "version": version,
        "metrics": metrics,
        "features": features,
        "artifact_path": model_path
    }
    save_model_metadata(metadata)
    logger.info(f"Model {pipeline_name} saved successfully with metrics: {metrics}")
    return True


def load_model_bundle(pipeline_name: str):
    """
    Loads saved model bundle (.joblib). Returns None if not found.
    """
    ensure_models_dir()
    model_path = os.path.join(MODELS_DIR, f"{pipeline_name}.joblib")
    if os.path.exists(model_path):
        try:
            return joblib.load(model_path)
        except Exception as e:
            logger.error(f"Error loading model bundle {pipeline_name}: {e}")
    return None
