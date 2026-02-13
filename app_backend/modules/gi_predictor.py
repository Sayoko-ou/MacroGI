# app_backend/modules/gi_predictor.py
import joblib
import pandas as pd
import os

# Get the directory where this file is located
_current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level from modules/ to app_backend/, then into models/
_app_backend_dir = os.path.dirname(_current_dir)
MODEL_PATH = os.path.join(_app_backend_dir, "models", "best_random_forest_model.pkl")
FEATURE_NAMES_PATH = os.path.join(_app_backend_dir, "models", "feature_names.pkl")

# 1. Try to load model and feature names
regressor = None
feature_names = None

if os.path.exists(MODEL_PATH):
    try:
        regressor = joblib.load(MODEL_PATH)
        print("GI Model Loaded")
    except Exception as e:
        print(f"GI Model file exists but failed to load: {e}")
else:
    print(f"ℹGI Model not found at: {MODEL_PATH}")
    print(f"   Current working directory: {os.getcwd()}")
    print("   Using Math Fallback.")

# Load feature names if available
if os.path.exists(FEATURE_NAMES_PATH):
    try:
        feature_names = joblib.load(FEATURE_NAMES_PATH)
        print(f"Feature names loaded: {list(feature_names)}")
    except:
        print("Feature names file exists but failed to load.")
        # Fallback to default feature names
        feature_names = ['Sugar_g', 'Fiber_g', 'Carbohydrate_g', 'Fat_g', 'Protein_g', 'Sodium_g']
else:
    # Fallback to default feature names
    feature_names = ['Sugar_g', 'Fiber_g', 'Carbohydrate_g', 'Fat_g', 'Protein_g', 'Sodium_g']

def predict_gi_sklearn(nutrients):
    if regressor is None:
        return None
    
    try:
        # Map feature names to nutrient dictionary keys
        # Handles variations like 'Sugar_g', 'Sugar', etc.
        def get_feature_value(feature_name):
            feature_lower = feature_name.lower()
            if 'sugar' in feature_lower:
                return nutrients.get('sugar', 0)
            elif 'fiber' in feature_lower:
                return nutrients.get('fiber', 0)
            elif 'carbohydrate' in feature_lower or 'carb' in feature_lower:
                return nutrients.get('carbs', 0)
            elif 'fat' in feature_lower:
                return nutrients.get('fat', 0)
            elif 'protein' in feature_lower:
                return nutrients.get('protein', 0)
            elif 'sodium' in feature_lower:
                return nutrients.get('sodium', 0)
            else:
                return 0
        
        # Create DataFrame with features in the exact order expected by the model
        features_dict = {name: get_feature_value(name) for name in feature_names}
        features = pd.DataFrame([features_dict])
        
        # Ensure columns are in the correct order
        features = features[feature_names]
        
        predicted = regressor.predict(features)[0]
        return float(predicted)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return None