import cv2
import numpy as np
import re
from rapidocr_onnxruntime import RapidOCR
from deep_translator import GoogleTranslator 
import os

ocr = RapidOCR()
table_model = None
translator = GoogleTranslator(source='auto', target='en')

def load_models(model_path="models/table_classifier.keras"):
    global table_model
    if os.path.exists(model_path):
        try:
            import tensorflow as tf
            table_model = tf.keras.models.load_model(model_path)
        except: table_model = None

def translate_if_foreign(text):
    if not all(ord(c) < 128 for c in text):
        try: return translator.translate(text).lower()
        except: return text.lower()
    return text.lower()

def convert_salt_to_sodium(extracted):
    salt = extracted.pop("Salt_tmp", 0) 
    if salt > 0 and extracted.get("Sodium", 0) == 0:
        extracted["Sodium"] = round((salt / 2.5) * 1000, 2)
    return extracted

def parse_value(text):
    clean = text.lower().replace('o', '0').replace('l', '1')
    match = re.search(r'(\d+(?:\.\d+)?)\s?([a-zA-Z%]+)?', clean)
    if match:
        return float(match.group(1)), match.group(2) if match.group(2) else "", text
    return None, None, None

def extract_nutrients(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    ocr_input = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    result, _ = ocr(ocr_input)
    if not result: return {"error": "No text detected", "success": False}

    # Using 'Calories'
    extracted = {
        "Calories": 0, "Protein": 0, "Total Fat": 0, 
        "Carbohydrate": 0, "Fiber": 0, "Sodium": 0, "Salt_tmp": 0 
    }
    
    target_nutrients = {
        "Calories": ["energy", "kcal", "calories"],
        "Protein": ["protein"],
        "Total Fat": ["total fat", "fat"],
        "Carbohydrate": ["carbohydrate", "carb", "carbs"],
        "Fiber": ["fibre", "fiber", "dietary fiber"],
        "Sodium": ["sodium"],
        "Salt_tmp": ["salt"]
    }

    for std_key, aliases in target_nutrients.items():
        for i, item in enumerate(result):
            raw_text = item[1]
            current_text = raw_text.lower()
            matched = any(alias in current_text for alias in aliases)
            
            if not matched:
                translated = translate_if_foreign(raw_text)
                if any(alias in translated for alias in aliases):
                    current_text = translated
                    matched = True
            
            if matched and len(current_text) < 35:
                v_num, v_unit, _ = parse_value(current_text)
                if v_num is not None:
                    extracted[std_key] = v_num
                    break
    
    extracted = convert_salt_to_sodium(extracted)

    return {
        "nutrients": extracted,
        "success": True
    }

load_models()