from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import Optional
# Import your AI modules
from modules.gi_predictor import predict_gi_sklearn
from modules.genai_advisor import get_food_fact
from modules.ocr_engine import extract_nutrients
from modules.insulin_predictor import predict_insulin_dosage
from modules.supabase_client import save_gi_gl_endpoint 

app = FastAPI()

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
    predicted_gi = max(0, min(100, int(predicted_gi)))
    
    # --- PROCESS 2: CALCULATE GL (Glycemic Load) = (GI * carb) / 100 ---
    # Get carbohydrate value (handle different key variations)
    carbs = float(normalized_nutrients.get('carbohydrate', 0) or 
                  normalized_nutrients.get('carbs', 0) or 0)
    
    predicted_gl = (predicted_gi * carbs) / 100
    
    # --- PROCESS 3: WEICONG'S MODEL (Insulin) ---
    # It needs the result from Process 1
    suggested_insulin = predict_insulin_dosage(normalized_nutrients, predicted_gi)
    
    # --- PROCESS 4: GENAI (Advisor) ---
    ai_tip = get_food_fact(request.food_name, normalized_nutrients, predicted_gi)
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
    supabase_result = save_gi_gl_endpoint(predicted_gi, predicted_gl)
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