from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv

load_dotenv()

class MacroGIBot:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = "models/gemini-flash-lite-latest"
        
        # 1. Load the Knowledge Base
        # Assuming you placed it in the root or a 'data' folder
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Adjusted to find data folder from app_backend/modules/
        kb_path = os.path.join(current_dir, "..", "..", "data", "knowledge_base.json")
        
        try:
            with open(kb_path, "r") as f:
                self.kb = json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Warning: Knowledge base not found at {kb_path}")
            self.kb = {"concepts": []}

        self.sys_instruct = (
            "You are the MacroGI Advisor. Help diabetics with dietary advice using Glycemic Index data."
            "Use the provided context to answer accurately. If no context is provided, "
            "rely on your general medical knowledge but remain conservative. "
            "Keep responses concise."
        )

    def _get_relevant_context(self, user_text):
        """Simple keyword matcher to pull data from JSON."""
        query = user_text.lower()
        context_parts = []
        
        for item in self.kb.get("concepts", []):
            # Check if any keyword from the JSON is in the user's message
            if any(keyword.lower() in query for keyword in item.get("keywords", [])):
                context_parts.append(f"{item['topic']}: {item['content']}")
        
        return "\n".join(context_parts)

    def get_advice(self, user_text):
        try:
            # 2. Inject Context
            context = self._get_relevant_context(user_text)
            
            # Combine context with the user's actual question
            # This is the "Augmented" part of RAG
            prompt_with_context = f"Context Information:\n{context}\n\nUser Question: {user_text}"
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt_with_context,
                config=types.GenerateContentConfig(
                    system_instruction=self.sys_instruct
                )
            )
            return response.text
        except Exception as e:
            print(f"Connection attempt failed: {e}")
            return f"Error: {str(e)}"