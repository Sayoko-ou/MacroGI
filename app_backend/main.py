from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from modules.gi_predictor import predict_gi_sklearn
from modules.genai_advisor import get_food_fact
from modules.ocr_engine import extract_nutrients
from modules.insulin_predictor import predict_insulin_dosage 

app = FastAPI()

# Define the data we expect from Flask
class AnalysisRequest(BaseModel):
    food_name: str
    nutrients: dict # {'sugar': 12, 'fiber': 4 ...}


@app.post("/scan-food")
async def scan_food(file: UploadFile = File(...)):
    image_bytes = await file.read()
    data = extract_nutrients(image_bytes)
    return data


    
@app.post("/analyze-food")
async def analyze_food(request: AnalysisRequest):
    
    # --- PROCESS 1: TEAGAN'S MODEL (GI) ---
    predicted_gi = predict_gi_sklearn(request.nutrients)
    predicted_gi = max(0, min(100, int(predicted_gi)))
    
    # --- PROCESS 2: WEICONG'S MODEL (Insulin) ---
    # It needs the result from Process 1
    suggested_insulin = predict_insulin_dosage(request.nutrients, predicted_gi)
    
    # --- PROCESS 3: GENAI (Advisor) ---
    ai_tip = get_food_fact(request.food_name, request.nutrients, predicted_gi)
    
    # Determine Colors
    gi_color = '#28a745'
    if predicted_gi >= 55: gi_color = '#ffc107'
    if predicted_gi >= 70: gi_color = '#dc3545'

    return {
        "gi": predicted_gi,
        "gi_color": gi_color,
        "insulin_suggestion": suggested_insulin,  # <--- Sending this to Frontend
        "ai_message": ai_tip
    }