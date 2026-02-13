import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient # cite: 5.1

print("\n--- 🔍 DIAGNOSTIC: InferenceClient ---")
load_dotenv()

# Support for both naming conventions
api_key = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")

if not api_key:
    print("❌ ERROR: No API Key found in .env!")
    exit()

# Using the most stable Llama model for the free tier cite: 4.1
model_id = "meta-llama/Llama-3.1-8B-Instruct"

try:
    # 1. Initialize the client cite: 5.1
    client = InferenceClient(api_key=api_key) 

    print(f"🚀 Requesting chat completion for: {model_id}")

    # 2. Use the standardized chat completion method cite: 5.3
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "user", "content": "Say 'Inference Client is working'"}
        ],
        max_tokens=20
    )

    # 3. Extract and print results cite: 5.3
    content = response.choices[0].message.content
    print(f"✅ SUCCESS! Response: {content}")

except Exception as e:
    print(f"💥 Client Error: {e}")
    print("\n💡 Tip: If you get a 404 here, the model is likely currently 'gated' or offline.")