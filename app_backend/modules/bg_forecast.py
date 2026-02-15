"""
BG Forecast module — loads the trained LSTM model and scaler,
provides forecast_glucose() for the /forecast-bg endpoint.

Supports per-user fine-tuned models: if a user-specific model exists
at models/user_models/bg_forecast_user_{id}.keras it will be used
instead of the base model.
"""

import os
import json
import numpy as np
import joblib
from tensorflow import keras
from modules.bg_explainer import explain_forecast

# ── Paths (relative to app_backend/) ──
_MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
_MODEL_PATH = os.path.join(_MODEL_DIR, 'bg_forecast_lstm.keras')
_SCALER_PATH = os.path.join(_MODEL_DIR, 'bg_forecast_scaler.joblib')
_META_PATH = os.path.join(_MODEL_DIR, 'bg_forecast_meta.json')
_USER_MODEL_DIR = os.path.join(_MODEL_DIR, 'user_models')

# ── Load artifacts at import time ──
_model = None
_scaler = None
_meta = None

if os.path.exists(_MODEL_PATH):
    _model = keras.models.load_model(_MODEL_PATH)
    _scaler = joblib.load(_SCALER_PATH)
    with open(_META_PATH) as f:
        _meta = json.load(f)
else:
    print(f"[bg_forecast] Model not found at {_MODEL_PATH} — forecast disabled.")

# ── Cache for per-user models ──
_user_models: dict[str, keras.Model] = {}


def _get_model_for_user(user_id: str | None) -> keras.Model:
    """Return the user-specific model if it exists, otherwise the base model."""
    if user_id is None:
        return _model

    # Check cache first
    if user_id in _user_models:
        return _user_models[user_id]

    # Check disk
    user_model_path = os.path.join(
        _USER_MODEL_DIR, f"bg_forecast_user_{user_id}.keras")

    if os.path.exists(user_model_path):
        print(f"[bg_forecast] Loading fine-tuned model for user {user_id}")
        user_model = keras.models.load_model(user_model_path)
        _user_models[user_id] = user_model
        return user_model

    # Fall back to base model
    return _model


def invalidate_user_model_cache(user_id: str):
    """Remove a cached user model so the next request reloads from disk."""
    _user_models.pop(user_id, None)


def forecast_glucose(recent_readings: list[dict],
                     user_id: str | None = None,
                     explain: bool = False) -> dict:
    """
    Predict glucose at 30, 60, and 90 minutes ahead.

    Parameters
    ----------
    recent_readings : list[dict]
        Last 12 readings (60 min at 5-min intervals), each with keys:
        glucose, insulin, carbs, IOB, COB
        Ordered oldest → newest.
    user_id : str, optional
        If provided, use the per-user fine-tuned model when available.

    Returns
    -------
    dict with keys: pred_30min, pred_60min, pred_90min (mg/dL floats)

    Raises
    ------
    RuntimeError  if model is not loaded.
    ValueError    if input length is wrong.
    """
    model = _get_model_for_user(user_id)

    if model is None:
        raise RuntimeError("BG forecast model is not loaded.")

    feature_cols = _meta['feature_cols']
    input_len = _meta['input_len']

    if len(recent_readings) < input_len:
        raise ValueError(
            f"Need at least {input_len} readings, got {len(recent_readings)}.")

    # Use only the most recent `input_len` readings
    readings = recent_readings[-input_len:]

    # Build feature matrix (12, n_features)
    rows = []
    for i, r in enumerate(readings):
        # Compute time-of-day encoding from reading timestamp if present,
        # otherwise use placeholder (features still scaled)
        hour_frac = 12.0  # default midday
        if 'timestamp' in r:
            from datetime import datetime
            ts = r['timestamp']
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            hour_frac = ts.hour + ts.minute / 60.0

        hour_sin = float(np.sin(2 * np.pi * hour_frac / 24))
        hour_cos = float(np.cos(2 * np.pi * hour_frac / 24))

        # Glucose rate of change (backward diff)
        if i == 0:
            glucose_roc = 0.0
        else:
            glucose_roc = float(r.get('glucose', 0)) - float(
                readings[i - 1].get('glucose', 0))

        row = [
            float(r.get('glucose', 0)),
            float(r.get('insulin', 0)),
            float(r.get('carbs', 0)),
            float(r.get('IOB', 0)),
            float(r.get('COB', 0)),
            hour_sin,
            hour_cos,
            glucose_roc,
        ]
        rows.append(row)

    X = np.array(rows, dtype=np.float32)           # (12, 8)
    X_scaled = _scaler.transform(X)                 # (12, 8)
    X_input = X_scaled.reshape(1, input_len, -1)    # (1, 12, 8)

    preds = model.predict(X_input, verbose=0)[0]    # (3,)

    result = {
        "pred_30min": round(float(preds[0]), 1),
        "pred_60min": round(float(preds[1]), 1),
        "pred_90min": round(float(preds[2]), 1),
    }

    if explain:
        try:
            current_bg = float(recent_readings[-1].get('glucose', 0))
            explanations = explain_forecast(
                model, X_scaled, _scaler, _meta,
                current_bg=current_bg,
                pred_60=result["pred_60min"],
            )
            result["explanations"] = explanations
        except Exception as e:
            print(f"[bg_forecast] SHAP explanation failed: {e}")

    return result
