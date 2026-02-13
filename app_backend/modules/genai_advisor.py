import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

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

    # Updated prompt to include Glycemic Load (GL)
    prompt_messages = [
        {
            "role": "user", 
            "content": (
                f"Give a 10-word health tip for eating {food_name}. "
                f"Metrics: Glycemic Index {predicted_gi}, Glycemic Load {predicted_gl}. "
                f"Focus on the impact of these combined values."
            )
        }
    ]

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=prompt_messages,
            max_tokens=35, # Slightly increased to handle complex advice
            temperature=0.6
        )
        
        tip = response.choices[0].message.content.strip()
        # Cleaning up the response in case the AI gets wordy
        return tip if tip else "No tip generated."

    except Exception as e:
        print(f"💥 AI Error: {e}")
        # Soft fallback to keep the UI clean
        return "Combine with fiber and protein to manage glucose response."