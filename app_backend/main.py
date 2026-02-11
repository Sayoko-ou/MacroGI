from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from modules.gi_predictor import predict_gi_sklearn
from modules.genai_advisor import get_food_fact
from modules.ocr_engine import extract_nutrients

app = FastAPI()

# Define the data we expect from Flask
class AnalysisRequest(BaseModel):
    food_name: str
    nutrients: dict # {'sugar': 12, 'fiber': 4 ...}

@app.post("/scan-food")
async def scan_food(file: UploadFile = File(...)):
    # Read the file bytes
    image_bytes = await file.read()
    
    # Call your new refactored function
    data = extract_nutrients(image_bytes)
    
    return data

    
@app.post("/analyze-food")
async def analyze_food(request: AnalysisRequest):
    
    # 1. Run the Regression Model (Your Teammate's work)
    predicted_gi = predict_gi_sklearn(request.nutrients)
    
    # Clamp value between 0-100 just in case
    predicted_gi = max(0, min(100, int(predicted_gi)))
    
    # 2. Run the GenAI Model (Gemini)
    # We pass the GI we just calculated so the AI knows context
    ai_tip = get_food_fact(request.food_name, request.nutrients, predicted_gi)
    
    # 3. Determine Color Label
    color = '#28a745' # Green
    if predicted_gi >= 55: color = '#ffc107' # Orange
    if predicted_gi >= 70: color = '#dc3545' # Red

    return {
        "gi": predicted_gi,
        "gi_color": color,
        "ai_message": ai_tip
    }