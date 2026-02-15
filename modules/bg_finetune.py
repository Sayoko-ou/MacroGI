"""
Per-user fine-tuning for the BG forecast LSTM model.

Loads the base model, freezes the LSTM layer, and fine-tunes the Dense
head on a single user's CGM + meal data (transfer learning).
"""

import logging
import os
import json
import numpy as np
import joblib
from datetime import datetime, timedelta
from collections import defaultdict
from tensorflow import keras

from database import db

logger = logging.getLogger(__name__)

# ── Paths ──
_MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
_BASE_MODEL_PATH = os.path.join(_MODEL_DIR, 'bg_forecast_lstm.keras')
_SCALER_PATH = os.path.join(_MODEL_DIR, 'bg_forecast_scaler.joblib')
_META_PATH = os.path.join(_MODEL_DIR, 'bg_forecast_meta.json')
_USER_MODEL_DIR = os.path.join(_MODEL_DIR, 'user_models')

# Load meta + scaler once
with open(_META_PATH) as f:
    _meta = json.load(f)

_scaler = joblib.load(_SCALER_PATH)

INPUT_LEN = _meta['input_len']       # 12
HORIZONS = _meta['horizons']         # [6, 12, 18]
FEATURE_COLS = _meta['feature_cols']  # 8 features
MIN_READINGS = 288  # 24 hours at 5-min intervals


def _build_time_series(cgm_rows: list[dict], meal_rows: list[dict]) -> np.ndarray:
    """
    Align CGM + meal data onto a 5-min grid and compute all 8 features.

    Returns array of shape (N, 8) with columns matching FEATURE_COLS.
    """
    if not cgm_rows:
        return np.empty((0, len(FEATURE_COLS)))

    # Build meal map keyed by 5-min-rounded timestamp
    meal_map: dict[str, dict] = defaultdict(lambda: {"carbs": 0.0, "insulin": 0.0})
    for m in meal_rows:
        m_ts = datetime.fromisoformat(m["created_at"])
        m_rounded = m_ts.replace(second=0, microsecond=0)
        m_rounded = m_rounded.replace(minute=(m_rounded.minute // 5) * 5)
        key = m_rounded.isoformat()
        meal_map[key]["carbs"] += float(m.get("carbs") or 0)
        meal_map[key]["insulin"] += float(m.get("insulin") or 0)

    # IOB/COB decay constants
    IOB_DECAY = 0.5 ** (5 / 75)
    COB_DECAY = 0.5 ** (5 / 45)

    # Sort CGM readings by timestamp
    cgm_rows = sorted(cgm_rows, key=lambda r: r["timestamp"])

    # Determine time range and walk a 5-min grid
    t_start = datetime.fromisoformat(cgm_rows[0]["timestamp"]).replace(second=0, microsecond=0)
    t_start = t_start.replace(minute=(t_start.minute // 5) * 5)
    t_end = datetime.fromisoformat(cgm_rows[-1]["timestamp"])

    # Index CGM readings by rounded timestamp for fast lookup
    cgm_map: dict[str, float] = {}
    for r in cgm_rows:
        r_ts = datetime.fromisoformat(r["timestamp"]).replace(second=0, microsecond=0)
        r_ts = r_ts.replace(minute=(r_ts.minute // 5) * 5)
        cgm_map[r_ts.isoformat()] = float(r["bg_value"])

    # Walk the grid
    iob, cob = 0.0, 0.0
    prev_glucose = None
    rows = []
    t = t_start
    while t <= t_end:
        key = t.isoformat()
        glucose = cgm_map.get(key)
        if glucose is None:
            t += timedelta(minutes=5)
            continue

        carbs_now = meal_map[key]["carbs"]
        insulin_now = meal_map[key]["insulin"]
        iob = iob * IOB_DECAY + insulin_now
        cob = cob * COB_DECAY + carbs_now

        hour_frac = t.hour + t.minute / 60.0
        hour_sin = float(np.sin(2 * np.pi * hour_frac / 24))
        hour_cos = float(np.cos(2 * np.pi * hour_frac / 24))
        glucose_roc = (glucose - prev_glucose) if prev_glucose is not None else 0.0

        rows.append([glucose, insulin_now, carbs_now, iob, cob,
                     hour_sin, hour_cos, glucose_roc])
        prev_glucose = glucose
        t += timedelta(minutes=5)

    return np.array(rows, dtype=np.float32)


def _create_sequences(data: np.ndarray):
    """
    Create sliding-window sequences from the aligned time series.

    Returns (X, Y) where:
      X shape: (n_samples, INPUT_LEN, n_features)
      Y shape: (n_samples, len(HORIZONS))
    """
    max_horizon = max(HORIZONS)
    X_list, Y_list = [], []

    for i in range(len(data) - INPUT_LEN - max_horizon + 1):
        x_window = data[i: i + INPUT_LEN]
        # Targets are glucose values at each horizon step ahead
        y_vals = [data[i + INPUT_LEN + h - 1, 0] for h in HORIZONS]
        X_list.append(x_window)
        Y_list.append(y_vals)

    return np.array(X_list), np.array(Y_list)


def finetune_for_user(user_id: str) -> dict:
    """
    Fine-tune the base BG forecast model on a specific user's data.

    Returns dict with keys: success, message, metrics (loss, mae).
    Raises RuntimeError if base model is missing.
    """
    if not os.path.exists(_BASE_MODEL_PATH):
        raise RuntimeError("Base model not found — cannot fine-tune.")

    # ── 1. Query user's CGM data ──
    cgm_resp = db.table("cgm_data") \
        .select("bg_value, timestamp") \
        .eq("patient_id", user_id) \
        .order("timestamp", desc=False) \
        .execute()
    cgm_rows = cgm_resp.data or []

    if len(cgm_rows) < MIN_READINGS:
        return {
            "success": False,
            "message": (
                f"Not enough data: {len(cgm_rows)} readings "
                f"(need at least {MIN_READINGS} = 24 h). "
                "Keep logging and try again later."
            ),
            "metrics": None,
        }

    # ── 2. Query user's meal/insulin data ──
    meal_resp = db.table("meal_data") \
        .select("carbs, insulin, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=False) \
        .execute()
    meal_rows = meal_resp.data or []

    # ── 3. Build aligned time series ──
    ts_data = _build_time_series(cgm_rows, meal_rows)
    if len(ts_data) < INPUT_LEN + max(HORIZONS):
        return {
            "success": False,
            "message": "Not enough aligned data points after grid alignment.",
            "metrics": None,
        }

    # ── 4. Scale features ──
    n_rows = ts_data.shape[0]
    ts_scaled = _scaler.transform(ts_data)  # (N, 8)

    # ── 5. Create sequences ──
    X, Y = _create_sequences(ts_scaled)
    if len(X) == 0:
        return {
            "success": False,
            "message": "Could not create any training sequences.",
            "metrics": None,
        }

    # Y targets are scaled glucose — we keep them in scaled space for
    # training since the base model was trained that way.
    # However, targets should be raw glucose values scaled individually.
    # Re-derive targets from the *unscaled* data, then scale only glucose col.
    # Actually the base model predicts raw mg/dL, so targets should be raw.
    _, Y_raw = _create_sequences(ts_data)

    logger.info("User %s: %d sequences, %d CGM readings, %d meal events.",
                user_id, len(X), len(cgm_rows), len(meal_rows))

    # ── 6. Load base model, freeze LSTM, unfreeze Dense ──
    model = keras.models.load_model(_BASE_MODEL_PATH)

    for layer in model.layers:
        if 'lstm' in layer.name.lower():
            layer.trainable = False
        else:
            layer.trainable = True

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-4),
        loss='mse',
        metrics=['mae'],
    )

    # ── 7. Fine-tune ──
    history = model.fit(
        X, Y_raw,
        epochs=15,
        batch_size=32,
        validation_split=0.15,
        verbose=1,
    )

    # ── 8. Save user model ──
    os.makedirs(_USER_MODEL_DIR, exist_ok=True)
    user_model_path = os.path.join(_USER_MODEL_DIR,
                                   f"bg_forecast_user_{user_id}.keras")
    model.save(user_model_path)
    logger.info("Saved fine-tuned model -> %s", user_model_path)

    # Return last-epoch metrics
    final_loss = float(history.history['loss'][-1])
    final_mae = float(history.history['mae'][-1])
    val_loss = float(history.history.get('val_loss', [0])[-1])
    val_mae = float(history.history.get('val_mae', [0])[-1])

    return {
        "success": True,
        "message": f"Fine-tuning complete for user {user_id}.",
        "metrics": {
            "loss": round(final_loss, 4),
            "mae": round(final_mae, 2),
            "val_loss": round(val_loss, 4),
            "val_mae": round(val_mae, 2),
            "epochs": len(history.history['loss']),
            "sequences": len(X),
        },
    }
