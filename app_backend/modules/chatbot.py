from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# 1. Load the variables from the .env file
load_dotenv()

class MacroGIBot:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        # Remove the http_options version override for now
        self.client = genai.Client(api_key=api_key)

        # Use the full model path
        self.model_id = "models/gemini-flash-lite-latest"
        self.sys_instruct = (
            "You are the MacroGI Advisor. Help diabetics with dietary advice "
            "using Glycemic Index data. Always include a medical disclaimer."
        )

    def get_advice(self, user_text):
        try:
            # We use the 'system_instruction' parameter directly in the call
            # This is the cleanest way supported by the 'google-genai' SDK
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=self.sys_instruct
                )
            )
            return response.text
        except Exception as e:
            # Check if it's a 404 again and print exactly what the client tried to reach
            print(f"Connection attempt failed: {e}")
            return f"Error: {str(e)}"


advisor_bot = MacroGIBot()