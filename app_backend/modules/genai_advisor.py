# app_backend/modules/genai_advisor.py
import os
import requests
import json

# 1. Get your free token from: https://huggingface.co/settings/tokens
# 2. Paste it in your .env file or hardcode it for testing
HF_API_KEY = os.getenv("HF_API_KEY", None)

# We will use Mistral-7B-Instruct (A very smart, open-source model)
REPO_ID = "mistralai/Mistral-7B-Instruct-v0.3"
API_URL = f"https://api-inference.huggingface.co/models/{REPO_ID}"

def get_food_fact(food_name, nutrients, predicted_gi):
    
    # --- 1. CHECK KEY ---
    if not HF_API_KEY or HF_API_KEY.startswith("PASTE"):
        return "MOCK TIP: Please add a Hugging Face Access Token to use open-source AI."

    # --- 2. PREPARE PROMPT (Formatted for Mistral) ---
    # Open source models work best with precise instructions
    prompt_text = f"""[INST] 
    You are a nutritionist. Give a 1-sentence advice on how to eat '{food_name}' to reduce glucose spikes.
    Context: It has a GI of {predicted_gi}. 
    Keep it under 20 words.
    [/INST]
    """

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": prompt_text,
        "parameters": {
            "max_new_tokens": 60, # Keep response short
            "return_full_text": False # Don't repeat the question back
        }
    }

    # --- 3. CALL HUGGING FACE API ---
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            # HuggingFace returns a list of dicts: [{'generated_text': '...'}]
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '').strip()
            return "No advice generated."
        
        elif response.status_code == 503:
            return "AI Model is loading (Cold Boot). Try again in 20s."
        else:
            print(f"HF Error {response.status_code}: {response.text}")
            return "Could not connect to Open Source AI."

    except Exception as e:
        print(f"Connection Error: {e}")
        return "AI Service Unavailable."