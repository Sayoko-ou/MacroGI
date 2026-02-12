# Feel free to edit with your actual functions

import os

# Placeholder for WeiCong's model loading
MODEL_PATH = "models/insulin_model.pkl"

def predict_insulin_dosage(nutrients, gi_value):
    """
    Simulates WeiCong's logic:
    Takes Nutrient Data + Teagan's GI Prediction -> Suggests Insulin Units
    """
    
    # 1. Get Carbs (The main driver for insulin)
    carbs = float(nutrients.get('carbohydrate', 0))
    if carbs == 0: carbs = float(nutrients.get('carbs', 0)) # Handle spelling diffs
    
    # 2. Logic: Standard is often 1 unit per 10g carbs (ICR 1:10)
    # We adjust it based on GI. If GI is high, maybe we suggest slightly more?
    base_dosage = carbs / 10.0
    
    # GI Multiplier: 
    # Low GI (0-55) -> 1.0x (Standard)
    # Med GI (56-69)-> 1.1x
    # High GI (70+) -> 1.2x
    multiplier = 1.0
    if gi_value > 55: multiplier = 1.1
    if gi_value > 70: multiplier = 1.2
    
    suggested_units = base_dosage * multiplier
    
    # Round to nearest 0.5 unit (Insulin pens usually do 0.5 steps)
    return round(suggested_units * 2) / 2