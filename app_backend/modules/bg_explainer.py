"""
SHAP Explainability for BG Forecast — uses GradientExplainer to compute
per-feature importance for each prediction horizon (30/60/90 min).

Aggregates SHAP values across 12 timesteps into a single importance
score per feature, merges hour_sin + hour_cos into "Time of Day".
"""

import numpy as np

# Feature names matching the order in bg_forecast.py row construction
_RAW_FEATURES = [
    "glucose", "insulin", "carbs", "IOB", "COB",
    "hour_sin", "hour_cos", "glucose_roc",
]

# Human-readable labels for the frontend
_DISPLAY_NAMES = {
    "glucose": "Glucose Level",
    "insulin": "Insulin Dose",
    "carbs": "Carbs Intake",
    "IOB": "Insulin on Board",
    "COB": "Carbs on Board",
    "time_of_day": "Time of Day",
    "glucose_roc": "Glucose Trend",
}

_HORIZON_LABELS = ["30min", "60min", "90min"]


def explain_forecast(model, X_scaled: np.ndarray, scaler, meta: dict,
                     current_bg: float = None, pred_60: float = None) -> dict:
    """
    Compute SHAP feature importances for a BG forecast prediction.

    Parameters
    ----------
    model : keras.Model
        The loaded LSTM model (base or per-user).
    X_scaled : np.ndarray
        Scaled input array, shape (12, 8).
    scaler : sklearn scaler
        The fitted scaler (not used directly, kept for future reference).
    meta : dict
        Model metadata containing feature_cols, input_len, etc.
    current_bg : float, optional
        Current glucose reading (latest value) for direction summary.
    pred_60 : float, optional
        Predicted glucose at 60 minutes for direction summary.

    Returns
    -------
    dict with keys per horizon ("30min", "60min", "90min") mapping
    feature display names to contribution values, plus a "summary" key
    with a natural language explanation.
    """
    try:
        import shap
    except ImportError:
        return {"error": "shap package not installed"}

    X_input = X_scaled.reshape(1, meta["input_len"], -1)  # (1, 12, 8)

    # Use a zero background (neutral baseline) for GradientExplainer
    background = np.zeros_like(X_input)

    explainer = shap.GradientExplainer(model, background)
    shap_values = explainer.shap_values(X_input)
    # shap 0.49+ returns a single array (1, 12, 8, 3) instead of a list of 3
    # Normalise to a list of 3 arrays each of shape (1, 12, 8)
    if isinstance(shap_values, np.ndarray) and shap_values.ndim == 4:
        shap_values = [shap_values[:, :, :, i] for i in range(shap_values.shape[-1])]

    explanations = {}

    for i, horizon in enumerate(_HORIZON_LABELS):
        sv = shap_values[i][0]  # (12, 8) — drop the batch dim

        # Aggregate across 12 timesteps: mean absolute value per feature
        feature_importance = np.mean(np.abs(sv), axis=0)  # (8,)

        # Also compute signed mean to know direction of contribution
        feature_signed = np.mean(sv, axis=0)  # (8,)

        # Build per-feature dict, merging hour_sin + hour_cos
        contrib = {}
        for j, feat in enumerate(_RAW_FEATURES):
            if feat in ("hour_sin", "hour_cos"):
                continue
            contrib[_DISPLAY_NAMES[feat]] = round(float(feature_signed[j]), 4)

        # Merge hour_sin (idx 5) + hour_cos (idx 6) into "Time of Day"
        tod_importance = float(feature_signed[5]) + float(feature_signed[6])
        contrib[_DISPLAY_NAMES["time_of_day"]] = round(tod_importance, 4)

        explanations[horizon] = contrib

    # Generate natural language summary based on 60min horizon (most relevant)
    # Use actual predictions to determine direction, not SHAP signs
    direction = None
    if current_bg is not None and pred_60 is not None:
        diff = pred_60 - current_bg
        if diff > 5:
            direction = "rise"
        elif diff < -5:
            direction = "drop"
        else:
            direction = "stable reading"
    summary = _generate_summary(explanations.get("60min", {}), direction)
    explanations["summary"] = summary

    return explanations


def _generate_summary(contrib: dict, direction: str = None) -> str:
    """Create a short natural language summary of the top contributing features."""
    if not contrib:
        return "Unable to generate explanation."

    # Sort by absolute contribution, descending
    sorted_feats = sorted(contrib.items(), key=lambda x: abs(x[1]), reverse=True)

    # Use provided direction (from actual predictions), fall back to SHAP signs
    if direction is None:
        total = sum(v for _, v in sorted_feats)
        if total > 0.01:
            direction = "rise"
        elif total < -0.01:
            direction = "drop"
        else:
            direction = "stable reading"

    # Top 2-3 contributors with percentage of total absolute contribution
    total_abs = sum(abs(v) for _, v in sorted_feats)
    if total_abs == 0:
        return "No significant drivers identified for this prediction."

    top_drivers = []
    for name, val in sorted_feats[:3]:
        pct = int(round(abs(val) / total_abs * 100))
        if pct < 5:
            continue
        sign = "+" if val > 0 else "-"
        top_drivers.append(f"{name} ({sign}{pct}%)")

    if not top_drivers:
        return "Prediction is driven by a balanced mix of factors."

    drivers_str = ", ".join(top_drivers)
    return f"Predicted {direction} mainly driven by: {drivers_str}."
