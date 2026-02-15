from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
# Import your AI modules
from modules.gi_predictor import predict_gi_sklearn
from modules.genai_advisor import get_food_fact
from modules.ocr_engine import extract_nutrients
from modules.insulin_predictor import predict_insulin_dosage
from modules.bg_forecast import forecast_glucose, invalidate_user_model_cache
from modules.bg_finetune import finetune_for_user
from modules.insulin_advisor import auto_isf_icr, advise_dose, compute_iob
from database import db, save_gi_gl

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 1. ADD THE PORT THAT YOUR BROWSER IS CURRENTLY USING
# If your browser address bar says localhost:5173 or 3000, put that here.
origins = [
    "http://localhost:8000",   # Your FastAPI port
    "http://127.0.0.1:8000",
    "http://localhost:5000",   # Common alternative port
    "http://localhost:3000",   # Common React port
     "*"                      # UNCOMMENT THE LINE BELOW IF YOU JUST WANT IT TO WORK
    # "null"                   # Sometimes needed for local file execution
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Using "*" is the "Nuclear Option" to stop all CORS errors
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    food_name: Optional[str] = "Unknown Food"
    nutrients: dict 

@app.post("/scan-food")
async def scan_food(file: UploadFile = File(...)):
    image_bytes = await file.read()
    data = extract_nutrients(image_bytes)
    return data


    
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


@app.post("/analyze-food")
async def analyze_food(request: AnalysisRequest):
    
    # Normalize nutrients to handle both OCR format and lowercase format
    normalized_nutrients = normalize_nutrients(request.nutrients)
    
    # --- PROCESS 1: TEAGAN'S MODEL (GI) ---
    predicted_gi = predict_gi_sklearn(normalized_nutrients)
    
    # --- PROCESS 2: CALCULATE GL (Glycemic Load) = (GI * carb) / 100 ---
    # Get carbohydrate value (handle different key variations)
    carbs = float(normalized_nutrients.get('carbohydrate', 0) or 
                  normalized_nutrients.get('carbs', 0) or 0)
    
    predicted_gl = (predicted_gi * carbs) / 100
    
    # --- PROCESS 3: WEICONG'S MODEL (Insulin) ---
    # It needs the result from Process 1
    suggested_insulin = predict_insulin_dosage(normalized_nutrients, predicted_gi)
    
    # --- PROCESS 4: GENAI (Advisor) ---
    ai_tip = get_food_fact(request.food_name, normalized_nutrients, predicted_gi, predicted_gl)

    
    return {
        "gi": int(predicted_gi),
        "gl": int(predicted_gl),
        "gi_color": "#28a745" if predicted_gi < 55 else "#dc3545",
        "ai_message": ai_tip
    }

@app.post("/analyze-food")
async def analyze_food(request: AnalysisRequest):

    # --- PROCESS 1: TEAGAN'S MODEL (GI) ---
    predicted_gi, predicted_gl = predict_gi_sklearn(request.nutrients)
    
    # --- PROCESS 2: WEICONG'S MODEL (Insulin) ---
    suggested_insulin = predict_insulin_dosage(request.nutrients, predicted_gi)
    
    # --- PROCESS 3: GENAI (Advisor) ---
    ai_tip = get_food_fact(request.food_name, request.nutrients, predicted_gi, predicted_gl)
    
    # GI Color Logic
    gi_color = '#28a745'
    if predicted_gi >= 55: gi_color = '#ffc107'
    if predicted_gi >= 70: gi_color = '#dc3545'

    # --- PROCESS 5: SAVE TO SUPABASE ---
    # Send GI and GL to Supabase endpoint
    supabase_result = save_gi_gl(predicted_gi, predicted_gl)
    if supabase_result.get("error"):
        print(f"⚠️ Supabase save failed: {supabase_result['error']}")
    else:
        print(f"✅ Saved to Supabase: GI={predicted_gi}, GL={predicted_gl}")

    return {
        "gi": predicted_gi,
        "gl": round(predicted_gl, 2),  # Round to 2 decimal places
        "gi_color": gi_color,
        "insulin_suggestion": suggested_insulin,  # <--- Sending this to Frontend
        "ai_message": ai_tip,
        "supabase_status": "success" if not supabase_result.get("error") else "failed",
        "gl": predicted_gl,
        "gi_color": gi_color,
        "insulin_suggestion": suggested_insulin,
        "ai_message": ai_tip
    }


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
   
    db.table("cgm_data").insert({
        "patient_id": data.user_id,
        "bg_value": data.bg_value,
        "timestamp": data.timestamp.isoformat()
    }).execute()

    

    return {"status": "success"}


from datetime import datetime, timedelta
from collections import defaultdict

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
    readings_dicts = [r.model_dump() for r in request.readings]
    result = forecast_glucose(readings_dicts)
    return result



@app.get("/api/glucose-stats")
async def get_glucose_stats(user_id: str):
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

    # 4. Simple Logic for AI Insight
    avg_glucose = sum(d["y"] for d in chart_data) / len(chart_data)
    insight = f"Your average glucose is {avg_glucose:.1f} mg/dL. "
    insight += "You are staying well within your target range today." if avg_glucose < 140 else "Consider a light walk to help lower your current trend."

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
        for m in meal_events:
            m_ts = datetime.fromisoformat(m["created_at"])
            # Round to nearest 5 min
            m_rounded = m_ts.replace(second=0, microsecond=0)
            minute = m_rounded.minute
            m_rounded = m_rounded.replace(minute=(minute // 5) * 5)
            key = m_rounded.isoformat()
            meal_map[key]["carbs"] += float(m.get("carbs") or 0)
            meal_map[key]["insulin"] += float(m.get("insulin") or 0)

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

            print(readings_for_model)

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
            print(f"Forecast error: {e}")

    return {
        "chart_data": chart_data,
        "forecast_data": forecast_data,
        "explanations": explanations,
        "latest": {
            "value": latest_reading["bg_value"],
            "time": datetime.fromisoformat(latest_reading["timestamp"]).strftime("%H:%M")
        },
        "insights": insight
    }


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


# ─── Insulin Advisor Endpoints ───────────────────────────────────────

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
