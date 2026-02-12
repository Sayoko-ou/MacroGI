# app_backend/modules/gi_predictor.py
import joblib
import pandas as pd
import os

MODEL_PATH = os.path.join("models", "best_random_forest_model.pkl")

# 1. Try to load model
regressor = None
if os.path.exists(MODEL_PATH):
    try:
        regressor = joblib.load(MODEL_PATH)
        print("✅ GI Model Loaded")
    except:
        print("⚠️ Model file exists but failed to load.")
else:
    print("ℹ️ GI Model not found. Using Math Fallback.")

def predict_gi_sklearn(nutrients):
    # 2. REAL MODE
    if regressor:
        try:
            # Ensure these feature names match your teammate's training columns exactly!
            features = pd.DataFrame([{
                'Sugar_g': nutrients.get('sugar', 0),
                'Fiber_g': nutrients.get('fiber', 0),
                'Carbohydrate_g': nutrients.get('carbs', 0),
                'Fat_g': nutrients.get('fat', 0),
                'Protein_g': nutrients.get('protein', 0)
            }])
            return float(regressor.predict(features)[0])
        except Exception as e:
            print(f"Prediction Error: {e}")

    # 3. SAFE FALLBACK MODE (If no model or error)
    # Simple logic: High sugar = High GI, High Fiber = Low GI
    sugar = float(nutrients.get('sugar', 0))
    fiber = float(nutrients.get('fiber', 0))
    # Base 50, +1.5 per g sugar, -2 per g fiber
    estimated = 50 + (sugar * 1.5) - (fiber * 2)
    return max(10, min(100, estimated))