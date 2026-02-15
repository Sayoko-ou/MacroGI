import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Explicitly point to your .env.local file
load_dotenv()

url: str = os.getenv("URL")
key: str = os.getenv("KEY")

print(url,key)

db: Client = create_client(url, key)

def save_gi_gl(gi: float, gl: float, user_id: str = None, food_name: str = None):
    """
    Save GI and GL values to Supabase.
    
    Args:
        gi: Glycemic Index value
        gl: Glycemic Load value
        user_id: Optional user ID
        food_name: Optional food name
    
    Returns:
        dict: Response from Supabase or error message
    """
    if db is None:
        return {"error": "Supabase client not initialized"}
    
    try:
        # Prepare data to send
        data = {
            "gi": float(gi),
            "gl": float(gl)
        }
        
        # Add optional fields if provided
        if user_id:
            data["user_id"] = user_id
        if food_name:
            data["food_name"] = food_name
        
        # Insert into Supabase
        # Note: Adjust table name based on your Supabase schema
        response = db.table("food_entries").insert(data).execute()
        
        return {
            "status": "success",
            "data": response.data if hasattr(response, 'data') else None
        }
    except Exception as e:
        print(f"Error saving to Supabase: {e}")
        return {"error": str(e)}

