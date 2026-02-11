import google.generativeai as genai
import os

# Configure with your key (Best practice: use Environment Variables)
# For now, you can paste it, but don't upload the key to GitHub!
GENAI_API_KEY = "PASTE_YOUR_GOOGLE_API_KEY_HERE"
genai.configure(api_key=GENAI_API_KEY)

def get_food_fact(food_name, nutrients, predicted_gi):
    """
    Sends nutrient info to Gemini and gets a 1-sentence tip.
    """
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    I am analyzing a food item: {food_name}.
    It has the following nutritional profile per serving:
    - Sugar: {nutrients.get('sugar', 0)}g
    - Fiber: {nutrients.get('fiber', 0)}g
    - Carbs: {nutrients.get('carbs', 0)}g
    - Fat: {nutrients.get('fat', 0)}g
    
    Our predictive model estimated the Glycemic Index (GI) is {predicted_gi}.
    
    Based on this, provide ONE interesting health fact or a suggestion for how to eat this 
    to lower the glucose spike (e.g. "Pair with protein"). Keep it under 20 words.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"GenAI Error: {e}")
        return "Could not generate a tip at this time."