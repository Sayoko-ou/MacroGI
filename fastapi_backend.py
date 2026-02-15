"""FastAPI backend for MacroGI — handles OCR, GI prediction, CGM, and insulin advice."""
import logging
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import os

# Import your AI modules
from modules.gi_predictor import predict_gi_sklearn
from modules.genai_advisor import get_food_fact
from modules.ocr_engine import extract_nutrients
from modules.insulin_predictor import predict_insulin_dosage
from modules.bg_forecast import forecast_glucose, invalidate_user_model_cache
from modules.bg_finetune import finetune_for_user
from modules.insulin_advisor import auto_isf_icr, advise_dose, compute_iob
from database import db

from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

app = FastAPI()

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

def normalize_nutrients(nutrients):
    """
    Normalize nutrient keys from OCR format (e.g., "Carbohydrate", "Total Fat")
    to lowercase format expected by the model (e.g., "carbs", "fat")
    """
    normalized = {}
    key_mapping = {
        'carbohydrate': ['carbohydrate', 'carbs', 'carb'],
        'sugar': ['sugar', 'sugars'],
        'fiber': ['fiber', 'fibre', 'dietary fiber'],
        'fat': ['fat', 'total fat'],
        'protein': ['protein'],
        'sodium': ['sodium', 'salt'],
        'energy': ['energy', 'calories', 'kcal']
    }

    # Convert all keys to lowercase for matching
    nutrients_lower = {k.lower(): v for k, v in nutrients.items()}

    for target_key, possible_keys in key_mapping.items():
        for key in possible_keys:
            if key in nutrients_lower:
                normalized[target_key] = float(nutrients_lower[key] or 0)
                break

    return normalized


# =====================================================================
# OCR ENDPOINTS
# =====================================================================

class AnalysisRequest(BaseModel):
    food_name: Optional[str] = "Unknown Food"
    nutrients: dict

@app.post("/scan-food")
async def scan_food(file: UploadFile = File(...)):
    """Process an uploaded food label image through OCR."""
    image_bytes = await file.read()
    data = extract_nutrients(image_bytes)
    return data


# =====================================================================
# ANALYSIS ENDPOINTS
# =====================================================================

@app.post("/analyze-food")
async def analyze_food(request: AnalysisRequest):
    """Analyze food nutrients: predict GI/GL, suggest insulin, generate AI tip."""

    # --- PROCESS 1: NORMALIZE NUTRIENTS ---
    # Handles both OCR format ("Carbohydrate") and lowercase format ("carbs")
    normalized_nutrients = normalize_nutrients(request.nutrients)

    # --- PROCESS 2: TEAGAN'S MODEL (GI) ---
    # (If your teammate updated this function to return two values,
    # change this to: predicted_gi, predicted_gl = predict_gi_sklearn(...) )
    predicted_gi = predict_gi_sklearn(normalized_nutrients)

    # --- PROCESS 3: CALCULATE GL ---
    # Glycemic Load = (GI * carbs) / 100
    carbs = float(normalized_nutrients.get('carbohydrate', 0) or
                  normalized_nutrients.get('carbs', 0) or 0)
    predicted_gl = (predicted_gi * carbs) / 100
    
    # --- PROCESS 5: GENAI (Advisor) ---
    ai_tip = get_food_fact(request.food_name, normalized_nutrients, predicted_gi, predicted_gl)

    # --- PROCESS 6: GI COLOR LOGIC ---
    gi_color = '#28a745' # Default: Green (Low GI)
    if predicted_gi >= 55:
        gi_color = '#ffc107' # Yellow (Medium GI)
    if predicted_gi >= 70:
        gi_color = '#dc3545' # Red (High GI)

    # --- FINAL RETURN (Cleaned up, no duplicates) ---
    return {
        "gi": int(predicted_gi),
        "gl": round(predicted_gl, 0),
        "gi_color": gi_color,
        "ai_message": ai_tip,
    }


# =====================================================================
# CGM ENDPOINTS
# =====================================================================

class CgmData(BaseModel):
    user_id: int
    timestamp: datetime
    bg_value: float

class MealData(BaseModel):
    carbs: float
    timestamp: datetime
    insulin: float
    gi: float


@app.post("/cgms-data")
async def receive_cgm_data(data: CgmData):
    """Receive and store a CGM reading."""

    db.table("cgm_data").insert({
        "patient_id": data.user_id,
        "bg_value": data.bg_value,
        "timestamp": data.timestamp.isoformat()
    }).execute()

    return {"status": "success"}


class CgmReading(BaseModel):
    glucose: float
    insulin: float = 0.0
    carbs: float = 0.0
    IOB: float = 0.0
    COB: float = 0.0
    timestamp: Optional[str] = None

class ForecastRequest(BaseModel):
    readings: list[CgmReading]

@app.post("/forecast-bg")
async def forecast_bg(request: ForecastRequest):
    """Forecast blood glucose at 30/60/90 minutes ahead."""
    readings_dicts = [r.model_dump() for r in request.readings]
    result = forecast_glucose(readings_dicts)
    return result


def _generate_personal_insights(chart_data: list, data_points: list) -> list:
    """
    Analyse 24h glucose data and return a list of insight objects.
    Each insight: {icon, title, body, severity}
    severity: "good" | "warning" | "danger" | "info"
    """
    import math

    values = [d["y"] for d in chart_data]
    if not values:
        return [{"icon": "info", "title": "No Data", "body": "Not enough readings to generate insights.", "severity": "info"}]

    n = len(values)
    avg = sum(values) / n
    std = math.sqrt(sum((v - avg) ** 2 for v in values) / n) if n > 1 else 0
    cv = (std / avg * 100) if avg > 0 else 0
    latest = values[-1]
    min_val = min(values)
    max_val = max(values)

    # --- Time in Range (70-180 mg/dL) ---
    in_range = sum(1 for v in values if 70 <= v <= 180)
    below_range = sum(1 for v in values if v < 70)
    above_range = sum(1 for v in values if v > 180)
    tir_pct = round(in_range / n * 100)
    below_pct = round(below_range / n * 100)
    above_pct = round(above_range / n * 100)

    insights = []

    # 1. Time in Range
    if tir_pct >= 70:
        insights.append({
            "icon": "target",
            "title": "Time in Range",
            "body": f"{tir_pct}% of readings are within target (70-180 mg/dL). This meets the recommended >70% goal — great control today.",
            "severity": "good"
        })
    elif tir_pct >= 50:
        insights.append({
            "icon": "target",
            "title": "Time in Range",
            "body": f"{tir_pct}% of readings are within target (70-180 mg/dL). Aim for >70%. Consider reviewing meal timing and portions.",
            "severity": "warning"
        })
    else:
        insights.append({
            "icon": "target",
            "title": "Time in Range",
            "body": f"Only {tir_pct}% of readings are in range. {above_pct}% above and {below_pct}% below target. This needs attention.",
            "severity": "danger"
        })

    # 2. Glucose Variability (CV)
    if cv < 36:
        insights.append({
            "icon": "variability",
            "title": "Glucose Stability",
            "body": f"Your glucose variability (CV {cv:.0f}%) is stable. A CV below 36% indicates consistent glucose levels.",
            "severity": "good"
        })
    else:
        insights.append({
            "icon": "variability",
            "title": "High Glucose Swings",
            "body": f"Your glucose variability is elevated (CV {cv:.0f}%). Frequent swings between {min_val:.0f} and {max_val:.0f} mg/dL. Consider smaller, more frequent meals with lower GI foods.",
            "severity": "warning"
        })

    # 3. Hypo Episodes (< 70 mg/dL)
    if below_range > 0:
        # Find consecutive hypo episodes
        hypo_episodes = 0
        in_hypo = False
        lowest_hypo = float('inf')
        for v in values:
            if v < 70:
                if not in_hypo:
                    hypo_episodes += 1
                    in_hypo = True
                lowest_hypo = min(lowest_hypo, v)
            else:
                in_hypo = False

        severity = "danger" if lowest_hypo < 54 else "warning"
        body = f"Detected {hypo_episodes} low glucose episode{'s' if hypo_episodes > 1 else ''} (below 70 mg/dL), reaching as low as {lowest_hypo:.0f} mg/dL."
        if lowest_hypo < 54:
            body += " Readings below 54 mg/dL are clinically significant — review insulin dosing with your care team."
        else:
            body += " Consider reducing insulin dose before similar activities or having a fast-acting carb on hand."

        insights.append({
            "icon": "hypo",
            "title": "Low Glucose Alert",
            "body": body,
            "severity": severity
        })

    # 4. Hyper Episodes (> 180 mg/dL)
    if above_range > 0:
        hyper_episodes = 0
        in_hyper = False
        peak_hyper = 0
        for v in values:
            if v > 180:
                if not in_hyper:
                    hyper_episodes += 1
                    in_hyper = True
                peak_hyper = max(peak_hyper, v)
            else:
                in_hyper = False

        severity = "danger" if peak_hyper > 250 else "warning"
        body = f"Detected {hyper_episodes} high glucose episode{'s' if hyper_episodes > 1 else ''} (above 180 mg/dL), peaking at {peak_hyper:.0f} mg/dL."
        if peak_hyper > 250:
            body += " Sustained highs above 250 mg/dL increase risk of complications. Review carb intake and insulin timing."
        else:
            body += " Post-meal spikes can be reduced by pairing carbs with protein or fat, or taking a short walk after eating."

        insights.append({
            "icon": "hyper",
            "title": "High Glucose Alert",
            "body": body,
            "severity": severity
        })

    # 5. Trend Analysis — last 30 min (6 readings)
    if n >= 6:
        recent = values[-6:]
        trend_diff = recent[-1] - recent[0]
        rate = trend_diff / 30  # mg/dL per minute

        if rate > 2:
            insights.append({
                "icon": "trend_up",
                "title": "Rapidly Rising",
                "body": f"Glucose has risen {trend_diff:.0f} mg/dL in the last 30 minutes ({rate:.1f} mg/dL/min). This may indicate a recent high-GI meal. Consider activity or correction.",
                "severity": "warning"
            })
        elif rate < -2:
            insights.append({
                "icon": "trend_down",
                "title": "Rapidly Dropping",
                "body": f"Glucose has dropped {abs(trend_diff):.0f} mg/dL in the last 30 minutes ({abs(rate):.1f} mg/dL/min). Monitor closely and have fast-acting carbs ready if needed.",
                "severity": "warning"
            })
        elif abs(trend_diff) < 10:
            insights.append({
                "icon": "trend_stable",
                "title": "Stable Trend",
                "body": f"Glucose has been steady over the last 30 minutes (currently {latest:.0f} mg/dL). Your current management is working well.",
                "severity": "good"
            })

    # 6. Dawn Phenomenon Detection — check if early morning readings (4-8 AM) are elevated
    timestamps_values = []
    for dp in data_points:
        try:
            ts = datetime.fromisoformat(dp["timestamp"])
            timestamps_values.append((ts.hour, dp["bg_value"]))
        except (ValueError, KeyError):
            continue

    dawn_readings = [v for h, v in timestamps_values if 4 <= h < 8]
    night_readings = [v for h, v in timestamps_values if 0 <= h < 4]

    if dawn_readings and night_readings:
        dawn_avg = sum(dawn_readings) / len(dawn_readings)
        night_avg = sum(night_readings) / len(night_readings)
        if dawn_avg - night_avg > 20:
            insights.append({
                "icon": "dawn",
                "title": "Dawn Phenomenon",
                "body": f"Your glucose rises an average of {dawn_avg - night_avg:.0f} mg/dL between midnight and early morning ({night_avg:.0f} → {dawn_avg:.0f} mg/dL). This is common and may be managed with basal insulin adjustments.",
                "severity": "info"
            })

    # 7. Post-Meal Spike Detection — look for sharp rises > 50 mg/dL within 2h windows
    if n >= 24:  # at least 2 hours of data
        spike_count = 0
        max_spike = 0
        for i in range(n - 24):
            window = values[i:i + 24]
            trough = min(window[:6])  # first 30 min
            peak = max(window[6:])   # next 90 min
            spike = peak - trough
            if spike > 50:
                spike_count += 1
                max_spike = max(max_spike, spike)

        # Only report if there are distinct spikes (not continuous high)
        if 0 < spike_count <= 10:
            insights.append({
                "icon": "spike",
                "title": "Post-Meal Spikes Detected",
                "body": f"Detected glucose spikes of up to {max_spike:.0f} mg/dL after meals. Pre-bolusing insulin 15-20 minutes before eating, or choosing lower-GI foods, can help flatten these spikes.",
                "severity": "warning"
            })

    # 8. Average Glucose & Estimated A1C
    estimated_a1c = (avg + 46.7) / 28.7
    if avg < 140:
        insights.append({
            "icon": "average",
            "title": "Daily Average",
            "body": f"Average glucose today is {avg:.0f} mg/dL (estimated A1C: {estimated_a1c:.1f}%). This is within a healthy range — keep it up.",
            "severity": "good"
        })
    elif avg < 180:
        insights.append({
            "icon": "average",
            "title": "Daily Average",
            "body": f"Average glucose today is {avg:.0f} mg/dL (estimated A1C: {estimated_a1c:.1f}%). Slightly elevated — consider increasing activity or reviewing carb portions.",
            "severity": "warning"
        })
    else:
        insights.append({
            "icon": "average",
            "title": "Daily Average",
            "body": f"Average glucose today is {avg:.0f} mg/dL (estimated A1C: {estimated_a1c:.1f}%). This is above target and warrants attention to diet and insulin dosing.",
            "severity": "danger"
        })

    return insights


@app.get("/api/glucose-stats")
async def get_glucose_stats(user_id: str):
    """Return glucose chart data, forecasts, and AI insights for a user."""
    # 1. Fetch last 24 hours of data for the chart
    yesterday = (datetime.now() - timedelta(hours=24)).isoformat()

    response = db.table("cgm_data") \
        .select("bg_value, timestamp") \
        .eq("patient_id", user_id) \
        .gt("timestamp", yesterday) \
        .order("timestamp", desc=False) \
        .execute()

    data_points = response.data

    if not data_points:
        return {"error": "No data found"}

    # 2. Format data for Chart.js [{x: time, y: value}]
    chart_data = [
        {"x": row["timestamp"], "y": row["bg_value"]}
        for row in data_points
    ]

    # 3. Get the very latest reading for the Card
    latest_reading = data_points[-1]

    # 4. Advanced AI Insights — pattern detection
    insights = _generate_personal_insights(chart_data, data_points)

    # 5. Run BG Forecast on the last 12 readings (60 min)
    #    Also pull meal_data to get real insulin & carb events
    forecast_data = None
    explanations = None
    if len(data_points) >= 12:
        last_12 = data_points[-12:]
        window_start = last_12[0]["timestamp"]

        # Fetch meals/insulin from meal_data within the last 4 hours
        # (IOB/COB decay needs history beyond the 60-min window)
        lookback = (datetime.fromisoformat(window_start) - timedelta(hours=4)).isoformat()
        meal_resp = db.table("meal_data") \
            .select("carbs, insulin, created_at") \
            .eq("user_id", user_id) \
            .gt("created_at", lookback) \
            .order("created_at", desc=False) \
            .execute()
        meal_events = meal_resp.data or []

        # Build a map: round each meal timestamp to nearest 5 min
        # and accumulate carbs/insulin per slot
        meal_map = defaultdict(lambda: {"carbs": 0.0, "insulin": 0.0})
        for meal in meal_events:
            m_ts = datetime.fromisoformat(meal["created_at"])
            # Round to nearest 5 min
            m_rounded = m_ts.replace(second=0, microsecond=0)
            minute = m_rounded.minute
            m_rounded = m_rounded.replace(minute=(minute // 5) * 5)
            key = m_rounded.isoformat()
            meal_map[key]["carbs"] += float(meal.get("carbs") or 0)
            meal_map[key]["insulin"] += float(meal.get("insulin") or 0)

        # Compute IOB and COB using exponential decay across the full
        # lookback window, then extract values for the last 12 readings
        IOB_DECAY = 0.5 ** (5 / 75)   # half-life 75 min per 5-min step
        COB_DECAY = 0.5 ** (5 / 45)   # half-life 45 min per 5-min step

        # Build full 5-min timeline from lookback to last reading
        t_start = datetime.fromisoformat(lookback).replace(second=0, microsecond=0)
        t_start = t_start.replace(minute=(t_start.minute // 5) * 5)
        t_end = datetime.fromisoformat(last_12[-1]["timestamp"])
        iob, cob = 0.0, 0.0
        iob_at_ts = {}
        cob_at_ts = {}
        t = t_start
        while t <= t_end:
            key = t.isoformat()
            carbs_now = meal_map[key]["carbs"]
            insulin_now = meal_map[key]["insulin"]
            iob = iob * IOB_DECAY + insulin_now
            cob = cob * COB_DECAY + carbs_now
            iob_at_ts[key] = iob
            cob_at_ts[key] = cob
            t += timedelta(minutes=5)

        # Build the 12 readings with real data
        readings_for_model = []
        for r in last_12:
            r_ts = datetime.fromisoformat(r["timestamp"])
            r_rounded = r_ts.replace(second=0, microsecond=0)
            minute = r_rounded.minute
            r_rounded = r_rounded.replace(minute=(minute // 5) * 5)
            key = r_rounded.isoformat()

            readings_for_model.append({
                "glucose": r["bg_value"],
                "insulin": meal_map[key]["insulin"],
                "carbs": meal_map[key]["carbs"],
                "IOB": iob_at_ts.get(key, 0.0),
                "COB": cob_at_ts.get(key, 0.0),
                "timestamp": r["timestamp"],
            })

        try:
            preds = forecast_glucose(readings_for_model, user_id=user_id, explain=True)
            last_ts = datetime.fromisoformat(latest_reading["timestamp"])
            forecast_data = [
                {"x": latest_reading["timestamp"], "y": latest_reading["bg_value"]},
                {"x": (last_ts + timedelta(minutes=30)).isoformat(), "y": preds["pred_30min"]},
                {"x": (last_ts + timedelta(minutes=60)).isoformat(), "y": preds["pred_60min"]},
                {"x": (last_ts + timedelta(minutes=90)).isoformat(), "y": preds["pred_90min"]},
            ]
            explanations = preds.get("explanations")
        except Exception as e:
            logger.error("Forecast error: %s", e)

    return {
        "chart_data": chart_data,
        "forecast_data": forecast_data,
        "explanations": explanations,
        "latest": {
            "value": latest_reading["bg_value"],
            "time": datetime.fromisoformat(latest_reading["timestamp"]).strftime("%H:%M")
        },
        "insights": insights
    }


# =====================================================================
# FORECAST & FINE-TUNING ENDPOINTS
# =====================================================================

class FinetuneRequest(BaseModel):
    user_id: str


@app.post("/api/finetune-model")
async def finetune_model(request: FinetuneRequest):
    """Trigger per-user fine-tuning of the BG forecast model."""
    try:
        result = finetune_for_user(request.user_id)
        # Invalidate cached model so the next forecast picks up the new one
        if result["success"]:
            invalidate_user_model_cache(request.user_id)
        return result
    except Exception as e:
        return {"success": False, "message": str(e), "metrics": None}


# =====================================================================
# INSULIN ADVISOR ENDPOINTS
# =====================================================================

@app.get("/api/auto-isf-icr")
async def get_auto_isf_icr(user_id: str):
    """Return auto-calculated ISF and ICR based on 7-day TDD."""
    try:
        result = auto_isf_icr(db, user_id)
        return result
    except Exception as e:
        return {"error": str(e)}


class InsulinAdviceRequest(BaseModel):
    user_id: str
    planned_carbs: float
    isf: Optional[float] = None
    icr: Optional[float] = None
    target_bg: float = 110


@app.post("/api/insulin-advice")
async def insulin_advice(request: InsulinAdviceRequest):
    """Calculate recommended insulin dose based on current BG, carbs, and IOB."""
    try:
        # 1. Get current BG from latest cgm_data
        bg_resp = db.table("cgm_data") \
            .select("bg_value") \
            .eq("patient_id", request.user_id) \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()

        if not bg_resp.data:
            return {"error": "No CGM data available. Please sync your sensor first."}

        current_bg = float(bg_resp.data[0]["bg_value"])

        # 2. Compute current IOB
        iob = compute_iob(db, request.user_id)

        # 3. Get ISF/ICR — use provided values or auto-calculate
        if request.isf and request.icr:
            isf = request.isf
            icr = request.icr
        else:
            auto = auto_isf_icr(db, request.user_id)
            isf = request.isf or auto["isf"]
            icr = request.icr or auto["icr"]

        # 4. Calculate dose
        result = advise_dose(
            current_bg=current_bg,
            target_bg=request.target_bg,
            planned_carbs=request.planned_carbs,
            iob=iob,
            isf=isf,
            icr=icr,
        )

        return result

    except Exception as e:
        return {"error": str(e)}
