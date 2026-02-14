import cv2
import numpy as np
import re
import base64
from collections import Counter
from rapidocr_onnxruntime import RapidOCR
from deep_translator import GoogleTranslator 
import os

# --- MODEL LOADING ---
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("⚠️ TensorFlow not found. Table detection will be skipped.")

ocr = RapidOCR()
table_model = None
translator = GoogleTranslator(source='auto', target='en')

def load_models(model_path="models/table_classifier.keras"):
    global table_model
    if TF_AVAILABLE and os.path.exists(model_path):
        try:
            table_model = tf.keras.models.load_model(model_path)
            print(f"✅ Table Detector loaded from {model_path}")
        except Exception as e:
            print(f"⚠️ Could not load Keras model: {e}")
            table_model = None
    else:
        print("ℹ️ Table detection model not found. Using full image OCR.")

# --- HELPER: VISUALIZATION ---
def draw_visuals(img, results, used_indices):
    """Draws boxes: Red for used data, Green for ignored text"""
    if not results or img is None: return None
    
    viz = img.copy()
    for i, item in enumerate(results):
        box = np.array(item[0]).astype(int)
        
        # Red if used, Green if ignored
        if i in used_indices:
            color = (0, 0, 255) # Red (BGR)
            thickness = 2
        else:
            color = (0, 255, 0) # Green (BGR)
            thickness = 1
            
        cv2.polylines(viz, [box], True, color, thickness)

    # Encode to Base64 string for HTML display
    _, buffer = cv2.imencode('.jpg', viz)
    return base64.b64encode(buffer).decode('utf-8')

# ==============================================================================
# 1. IMAGE PROCESSING & TABLE DETECTION
# ==============================================================================
def get_table_crop(img):
    """Attempts to crop the nutrition table using the AI model or CV contours."""
    if table_model is None:
        return img, False

    # Preprocessing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilate = cv2.dilate(thresh, kernel, iterations=4)
    contours, _ = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 50 and h > 50:
            crop = img[y:y+h, x:x+w]
            
            # AI Check
            c_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            ai_input = cv2.resize(c_gray, (128, 128))
            ai_input = np.expand_dims(ai_input, axis=-1)
            ai_input = np.expand_dims(ai_input, axis=0) / 255.0
            
            conf = table_model.predict(ai_input, verbose=0)[0][0]
            if conf > 0.5:
                candidates.append({'crop': crop, 'conf': conf})

    # Return best candidate
    candidates = sorted(candidates, key=lambda x: x['conf'], reverse=True)
    if candidates:
        return candidates[0]['crop'], True
    
    return img, False

# ==============================================================================
# 2. TEXT PARSING & VALIDATION
# ==============================================================================
def parse_value(text):
    """Extracts numeric value and unit from a string like '12g' or '100 kcal'"""
    clean = text.lower().replace('o', '0').replace('l', '1')
    match = re.search(r'(\d+(?:\.\d+)?)\s?([a-zA-Z%]+)?', clean)
    if match:
        val = float(match.group(1))
        unit = match.group(2) if match.group(2) else ""
        return val, unit, text
    return None, None, None

def is_physically_possible(nutrient, val, unit, text):
    """Sanity checks (e.g. Sodium can't be 100g)"""
    # If the text is way too long, it's probably a sentence, not a table value
    if len(text) > 15 or unit == "%": return False
    
    if nutrient == "Sodium":
        # FIXED: Allow empty units ("") because OCR often misses "mg"
        if unit != "" and unit not in ['mg', 'g']: return False
        
        # If unit is 'g', value shouldn't be huge (e.g., 500g salt is impossible)
        if unit == 'g' and val > 10: return False 
        return True
    
    if nutrient == "Energy":
        if unit in ['kcal', 'kj', 'cal', 'cals']: return True
        # If no unit, assume kcal if the number is significant
        if unit == "" and val > 5: return True
        return False
    
    # Default grams check for Protein, Fat, Carbs, Fiber
    if unit in ['kcal', 'kj', 'cal']: return False
    if unit in ['g', 'mg', 'mcg', '']: return True
    
    return False


    # Encode to Base64 string for HTML display
    _, buffer = cv2.imencode('.jpg', viz)
    return base64.b64encode(buffer).decode('utf-8')

def translate_if_foreign(text):
    if not all(ord(c) < 128 for c in text):
        try: return translator.translate(text).lower()
        except: return text.lower()
    return text.lower()


# ==============================================================================
# 3. DOMINANT COLUMN CLUSTERING (RESTORED LOGIC)
# ==============================================================================
def find_all_candidates(key_idx, key_box, all_results, used_indices, nutrient_name):
    """Finds all numbers to the right of a label (e.g. 'Protein')"""
    key_y = (key_box[0][1] + key_box[2][1]) / 2
    key_x = key_box[1][0]

    candidates = []
    for i, item in enumerate(all_results):
        if i == key_idx or i in used_indices: continue
        val_box, val_text = item[0], item[1]
        val_y = (val_box[0][1] + val_box[2][1]) / 2
        val_x = val_box[0][0]

        if val_x < key_x: continue # Must be to the right
        if abs(key_y - val_y) > 15: continue # Relaxed vertical drift check

        v_num, v_unit, v_raw = parse_value(val_text)
        if v_num is None: continue

        if is_physically_possible(nutrient_name, v_num, v_unit, val_text):
            candidates.append({
                'val': v_num,
                'idx': i,
                'x': val_x,
                'key': nutrient_name,
                'vertical_score': abs(key_y - val_y)
            })
    return candidates

def solve_column_clustering(candidates_pool):
    """Finds the vertical column where most numbers align"""
    all_x = []
    for key, cands in candidates_pool.items():
        for c in cands: all_x.append(c['x'])

    if not all_x: return {}

    # Find Dominant X (Bin size 40px)
    bins = [round(x / 40) * 40 for x in all_x]
    common = Counter(bins).most_common()
    if not common: return {}

    dominant_x = common[0][0]
    final_results = {}

    # Filter candidates by this column
    for key, cands in candidates_pool.items():
        if not cands: continue
        best_cand = None
        min_dist = float('inf')

        for c in cands:
            dist = abs(c['x'] - dominant_x)
            if dist < 60: # Within 60px of the invisible column line
                if dist < min_dist:
                    min_dist = dist
                    best_cand = c
        
        if best_cand:
            final_results[key] = best_cand

    return final_results

# ==============================================================================
# 4. MAIN EXTRACT FUNCTION
# ==============================================================================
def extract_nutrients(image_bytes):
    """
    Main entry point.
    Input: Image bytes
    Output: Dictionary of extracted nutrients + Annotated Image
    """
    # 1. Decode Image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 2. Crop Table
    target_img, found_table = get_table_crop(img)
    
    # 3. Run OCR
    ocr_input = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)
    result, _ = ocr(ocr_input)

    if not result:
        return {"error": "No text detected"}

    # 4. Search logic
    # Initializing with 0s to ensure the frontend always gets the expected keys
    extracted = {
        "Calories": 0, "Protein": 0, "Total Fat": 0, 
        "Carbohydrate": 0, "Fiber": 0, "Sodium": 0, "Salt": 0 
    }
    used_indices = set()
    candidates_pool = {}

    # Map standardized keys to possible OCR text variations
    target_nutrients = {
        "Calories": ["energy", "kcal", "calories"],
        "Protein": ["protein"],
        "Total Fat": ["total fat", "fat"],
        "Carbohydrate": ["carbohydrate", "carb", "carbs"],
        "Fiber": ["fibre", "fiber", "dietary fiber"],
        "Sodium": ["sodium"],
        "Salt": ["salt"]
    }

    # Pass 1: Find Labels and their Candidates
    # CRITICAL: We loop through standard nutrients first to avoid grabbing multiple labels for one key
    for std_key, aliases in target_nutrients.items():
        for i, item in enumerate(result):
            if i in used_indices: continue
            
            # Translate text to handle foreign nutrition labels
            raw_text = item[1]
            translated_text = translate_if_foreign(raw_text)
            box = item[0]

            if any(alias in translated_text for alias in aliases):
                # Ignore long strings that might be paragraphs/ingredients
                if len(translated_text) > 30: continue 

                # Case A: Value is inside the same text box (e.g., "Protein 5g")
                clean_text = translated_text
                for a in aliases: clean_text = clean_text.replace(a, "")
                v_num, v_unit, v_raw = parse_value(clean_text)
                
                # Check for "Calories" logic in sanity check
                # (Passing std_key as "Energy" to internal validator for back-compat)
                val_key = "Energy" if std_key == "Calories" else std_key
                
                if v_num is not None and is_physically_possible(val_key, v_num, v_unit, clean_text):
                    extracted[std_key] = v_num
                    used_indices.add(i)
                    break # Success! Move to the next nutrient in target_nutrients

                # Case B: Value is in a separate box (needs alignment)
                cands = find_all_candidates(i, box, result, used_indices, val_key)
                if cands:
                    candidates_pool[std_key] = cands
                    used_indices.add(i)
                    break # Success! Move to the next nutrient

    # Pass 2: Solve Alignment
    resolved = solve_column_clustering(candidates_pool)
    for k, cand in resolved.items():
        extracted[k] = cand['val']
        if 'idx' in cand: 
            used_indices.add(cand['idx'])

    # 5. DRAW VISUALS
    annotated_b64 = draw_visuals(target_img, result, used_indices)

    return {
        "nutrients": extracted,
        "table_detected": found_table,
        "annotated_image": annotated_b64
    }

# Initialize models when this module is imported
load_models()