# main.py
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import Optional # Add this for optional fields
# Import Teagan's second model
from modules.gi_predictor import predict_gi_sklearn, predict_gl_sklearn 
from modules.genai_advisor import get_food_fact
from modules.ocr_engine import extract_nutrients
from modules.insulin_predictor import predict_insulin_dosage 

app = FastAPI()

class AnalysisRequest(BaseModel):
    food_name: Optional[str] = "Unknown Food" # Make optional for GI calculation
    nutrients: dict 

@app.post("/analyze-food")
async def analyze_food(request: AnalysisRequest):
    # --- PROCESS 1: TEAGAN'S MODELS (GI & GL) ---
    predicted_gi, predicted_gl = predict_gi_sklearn(request.nutrients)
    
    # --- PROCESS 2: WEICONG'S MODEL (Insulin) ---
    suggested_insulin = predict_insulin_dosage(request.nutrients, predicted_gi)
    
    # --- PROCESS 3: GENAI (Advisor) ---
    # Now passing GL to the advisor as well
    ai_tip = get_food_fact(request.food_name, request.nutrients, predicted_gi, predicted_gl)
    
    # GI Color Logic
    gi_color = '#28a745'
    if predicted_gi >= 55: gi_color = '#ffc107'
    if predicted_gi >= 70: gi_color = '#dc3545'

    return {
        "gi": predicted_gi,
        "gl": predicted_gl, # Returning GL to frontend
        "gi_color": gi_color,
        "insulin_suggestion": suggested_insulin,
        "ai_message": ai_tip
    }