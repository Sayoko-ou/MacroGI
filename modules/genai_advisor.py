"""GenAI food advisor using HuggingFace Inference API (Llama 3.1)."""
import logging
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

load_dotenv()
HF_API_KEY = os.getenv("HF_TOKEN")

# Initialize client
client = InferenceClient(api_key=HF_API_KEY)

# Using Llama 3.1 for stable provider support
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

def get_food_fact(food_name, nutrients, predicted_gi, predicted_gl):
    """
    Generates a concise health tip using both GI and GL metrics.
    """
    if not HF_API_KEY or HF_API_KEY.startswith("PASTE"):
        return "Please add a valid HF Access Token to your .env file."

    prompt_messages = [
        {
            "role": "user",
            "content": (
                f"Write a single, practical 10-to-15 word dietary tip for eating {food_name}. "
                f"GI: {predicted_gi}, GL: {predicted_gl}, Nutrients: {nutrients}. "
                "CRITICAL INSTRUCTIONS: "
                "1. Do NOT use generic phrases like 'eat in moderation' or 'balance your GI'. "
                "2. If GI/GL is high, suggest a specific food pairing (like nuts or fiber) to slow blood sugar spikes. "
                "3. If GI/GL is low, highlight its benefit for sustained energy. "
                "4. Give direct, actionable advice without repeating the metrics."
            )
        }
    ]

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=prompt_messages,
            max_tokens=35,
            temperature=0.6
        )

        tip = response.choices[0].message.content.strip()
        # Cleaning up the response in case the AI gets wordy
        return tip if tip else "No tip generated."

    except Exception as e:
        logger.error("AI Error: %s", e)
        # Soft fallback to keep the UI clean
        return "Simulation: Offline."
