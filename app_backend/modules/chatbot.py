from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# 1. Load the variables from the .env file
load_dotenv()

class MacroGIBot:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)

        self.model_id = "gemini-1.5-flash"
        self.sys_instruct = (
            "You are the MacroGI Advisor. Help diabetics with dietary advice "
            "using Glycemic Index data. Always include a medical disclaimer."
        )

    def get_advice(self, user_text):
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=self.sys_instruct
                )
            )
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"


advisor_bot = MacroGIBot()