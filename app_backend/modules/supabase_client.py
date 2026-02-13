# app_backend/modules/supabase_client.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = None

try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase Client Connected")
    else:
        print("⚠️ Supabase credentials not found in environment variables")
except Exception as e:
    print(f"⚠️ Error initializing Supabase: {e}")


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
    if supabase is None:
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
        response = supabase.table("food_entries").insert(data).execute()
        
        return {
            "status": "success",
            "data": response.data if hasattr(response, 'data') else None
        }
    except Exception as e:
        print(f"Error saving to Supabase: {e}")
        return {"error": str(e)}


def save_gi_gl_endpoint(gi: float, gl: float):
    """
    Simple endpoint-style function that sends data to Supabase.
    This matches the user's requirement: send {"gi": 123, "gl": 12312} to endpoint
    
    Args:
        gi: Glycemic Index value
        gl: Glycemic Load value
    
    Returns:
        dict: Response status
    """
    return save_gi_gl(gi, gl)
