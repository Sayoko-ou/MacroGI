# app_backend/modules/genai_advisor.py
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient # cite: 5.1

load_dotenv()
HF_API_KEY = os.getenv("HF_TOKEN")

# Initialize clientcite: 5.1
client = InferenceClient(api_key=HF_API_KEY)

# THE FIX: Switch to Llama 3.1 which has wider provider support
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

def get_food_fact(food_name, nutrients, predicted_gi):
    if not HF_API_KEY or HF_API_KEY.startswith("PASTE"):
        return "Please add a valid HF Access Token to your .env file."

    # Using the standard chat messages format
    prompt_messages = [
        {
            "role": "user", 
            "content": f"Give a 10-word health tip for eating {food_name} (Glycemic Index: {predicted_gi})."
        }
    ]

    try:
        # The router will find a provider for Llama 3.1
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=prompt_messages,
            max_tokens=30,
            temperature=0.5
        )
        
        tip = response.choices[0].message.content.strip()
        return tip if tip else "No tip generated."

    except Exception as e:
        print(f"💥 AI Error: {e}")
        # Final fallback so your app never shows an error to the user
        return f"AI Error: {e}"