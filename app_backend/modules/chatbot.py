"""MacroGI chatbot using Google Gemini for dietary advice."""
import logging
from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

class MacroGIBot:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = "models/gemini-flash-lite-latest"

        # 1. Load the Knowledge Base
        current_dir = os.path.dirname(os.path.abspath(__file__))
        kb_path = os.path.join(current_dir, "knowledge_base.json")

        try:
            with open(kb_path, "r") as f:
                self.kb = json.load(f)
                logger.info("Knowledge base found!")
        except FileNotFoundError:
            logger.warning("Knowledge base not found at %s", kb_path)
            self.kb = {"concepts": []}

        self.sys_instruct = (
            "You are the MacroGI Advisor. Help diabetics with dietary advice using Glycemic Index data."
            "Use the provided context to answer accurately. If no context is provided, "
            "rely on your general medical knowledge but remain conservative. "
            "Keep responses concise. If you are given context with list of items, display them nicely."
        )

    def _get_relevant_context(self, user_text):
        query = user_text.lower()
        context_parts = []

        # 1. Check the 'concepts' section
        for item in self.kb.get("concepts", []):
            keywords = item.get("keywords", [])
            if any(kw.lower() in query for kw in keywords) or item['topic'].lower() in query:
                content = item.get("content") or ". ".join(item.get("content_list", []))
                context_parts.append(f"{item['topic']}: {content}")

        # 2. NEW: Check the 'macrogi_queries' section
        for item in self.kb.get("macrogi_queries", []):
            if any(word in query for word in item['query'].lower().split()):
                context_parts.append(f"Q: {item['query']}\nA: {item['response']}")

        # 3. Fallback: If they ask about the app/features and nothing was found
        if not context_parts and ("feature" in query or "macrogi" in query or "what can you do" in query):
            for item in self.kb.get("macrogi_queries", []):
                context_parts.append(f"Feature Info: {item['response']}")

        return "\n".join(context_parts)

    def get_advice(self, user_text):
        try:
            # 2. Inject Context
            context = self._get_relevant_context(user_text)

            # Combine context with prompt
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
            logger.error("Connection attempt failed: %s", e)
            return f"Error: {str(e)}"
