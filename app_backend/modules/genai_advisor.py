# app_backend/modules/genai_advisor.py
# app_backend/modules/genai_advisor.py
import os

# --- SAFE IMPORT BLOCK ---
try:
    import google.generativeai as genai
    HAS_GENAI_LIB = True
except ImportError:
    HAS_GENAI_LIB = False
    print("⚠️ Google GenAI library not found. AI tips will be mocked.")

# Get key safely
GENAI_API_KEY = os.getenv("GENAI_API_KEY", "")

def get_food_fact(food_name, nutrients, predicted_gi):
    # 1. CHECK MISSING LIBRARY
    if not HAS_GENAI_LIB:
        return f"MOCK TIP: Install 'google-generativeai' to get real AI tips for {food_name}."

    # 2. CHECK MISSING KEY
    if not GENAI_API_KEY or GENAI_API_KEY == "PASTE_YOUR_GOOGLE_API_KEY_HERE":
        return f"MOCK TIP: Add API Key to get real AI tips for {food_name}."

    # 3. REAL LOGIC
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Analyze this food: {food_name}.
        GI Score: {predicted_gi}.
        Nutrients: {nutrients}.
        Give a 1-sentence health tip to lower the glucose spike.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"GenAI Connection Error: {e}")
        return "Could not generate tip at this time."