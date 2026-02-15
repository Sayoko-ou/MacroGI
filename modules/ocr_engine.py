"""OCR engine for extracting nutritional data from food label images."""
import logging
import cv2
import numpy as np
import re
import base64
from collections import Counter
from rapidocr_onnxruntime import RapidOCR
from deep_translator import GoogleTranslator
import os

logger = logging.getLogger(__name__)

# --- Constants ---
MIN_CONTOUR_SIZE = 50       # Minimum width/height for table detection candidates
COLUMN_BIN_SIZE = 40        # Pixel bin size for column alignment clustering

# I'm using a try-except here because TensorFlow can be heavy.
# If it fails to load on whatever machine this runs on, the app won't crash,
# it just skips the smart table cropping part and scans the whole image.
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not found. Table detection will be skipped.")

ocr = RapidOCR()
table_model = None
translator = GoogleTranslator(source='auto', target='en')

def load_models(model_path="models/table_classifier.keras"):
    """Loads the Keras model once at startup so we don't have to reload it for every scan."""
    global table_model
    if TF_AVAILABLE and os.path.exists(model_path):
        try:
            table_model = tf.keras.models.load_model(model_path)
            logger.info("Table Detector loaded from %s", model_path)
        except Exception as e:
            logger.error("Could not load Keras model: %s", e)
            table_model = None
    else:
        logger.info("Table detection model not found. Using full image OCR.")

# Disable table model for demo.
table_model = None

# --- HELPER: VISUALIZATION ---
def draw_visuals(img, results, used_indices):
    """
    Creates the overlay image for the frontend so the user can see what the OCR did.
    Red boxes = data we actually extracted and used.
    Green boxes = text the OCR saw but we ignored.
    """
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

# Step 1: Image Processing & Cropping
def get_table_crop(img):
    """
    Instead of scanning the whole image (which might have logos and junk text),
    this tries to find the actual nutrition table contour and crop it out.
    """
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
        if w > MIN_CONTOUR_SIZE and h > MIN_CONTOUR_SIZE:
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

# Step 2: Text Parsing & Validation
def parse_value(text):
    """Takes a messy string like '12g' or '100 kcal' and splits it into the number and unit."""
    # Quick fix: OCR often confuses the letter 'O' with the number '0', and 'l' with '1'
    clean = text.lower().replace('o', '0').replace('l', '1')
    match = re.search(r'(\d+(?:\.\d+)?)\s?([a-zA-Z%]+)?', clean)
    if match:
        val = float(match.group(1))
        unit = match.group(2) if match.group(2) else ""
        return val, unit, text
    return None, None, None

def is_physically_possible(nutrient, val, unit, text):
    """
    Sanity check function. Sometimes OCR grabs random numbers (like a phone number).
    This ensures the number actually makes logical sense for that specific nutrient.
    """
    # If the text is way too long, it's probably an ingredient paragraph, not a table value
    if len(text) > 15 or unit == "%": return False

    if nutrient == "Sodium":
        # Allow empty units ("") because OCR often misses the tiny "mg" text
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


def translate_if_foreign(text):
    """Quick helper to translate foreign labels into English so the keyword matcher still works."""
    if not all(ord(c) < 128 for c in text):
        try: return translator.translate(text).lower()
        except Exception: return text.lower()
    return text.lower()


# Step 3: Column Clustering (Handling weird formatting)
def find_all_candidates(key_idx, key_box, all_results, used_indices, nutrient_name):
    """
    If the value isn't right next to the label, this function looks to the
    right of the label (e.g., 'Protein') to find all floating numbers that could be a match.
    """
    key_y = (key_box[0][1] + key_box[2][1]) / 2
    key_x = key_box[1][0]

    candidates = []
    for i, item in enumerate(all_results):
        if i == key_idx or i in used_indices: continue
        val_box, val_text = item[0], item[1]
        val_y = (val_box[0][1] + val_box[2][1]) / 2
        val_x = val_box[0][0]

        if val_x < key_x: continue # Must be to the right of the label
        if abs(key_y - val_y) > 15: continue # Must be roughly on the same horizontal line

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
    """
    Since nutrition tables usually have all their numbers lined up in a neat vertical column,
    this function calculates where that invisible column line is.
    It groups all the x-coordinates to find the most common alignment.
    """
    all_x = []
    for key, cands in candidates_pool.items():
        for c in cands: all_x.append(c['x'])

    if not all_x: return {}

    # Find the dominant X-coordinate (grouping them in COLUMN_BIN_SIZE px bins)
    bins = [round(x / COLUMN_BIN_SIZE) * COLUMN_BIN_SIZE for x in all_x]
    common = Counter(bins).most_common()
    if not common: return {}

    dominant_x = common[0][0]
    final_results = {}

    # Lock in the candidates that fall within 60px of our invisible column line
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

# Step 4: Main Extraction Pipeline
def extract_nutrients(image_bytes):
    """
    This is the main endpoint that FastAPI calls.
    It takes the raw image bytes, runs the whole OCR pipeline, and returns the JSON data.
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
    # Set default values to 0. This ensures the frontend doesn't crash expecting a key that doesn't exist.
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
    # Loop through my target list first, rather than the OCR results.
    # This stops the code from accidentally mapping two different values to the same nutrient.
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
    # Take all those floating numbers we found in Case B and lock them to the dominant column.
    resolved = solve_column_clustering(candidates_pool)
    for k, cand in resolved.items():
        extracted[k] = cand['val']
        if 'idx' in cand:
            used_indices.add(cand['idx'])

    # 5. Generate the visual feedback image
    annotated_b64 = draw_visuals(target_img, result, used_indices)

    return {
        "nutrients": extracted,
        "table_detected": found_table,
        "annotated_image": annotated_b64
    }

# Initialize models when this module is imported
load_models()
