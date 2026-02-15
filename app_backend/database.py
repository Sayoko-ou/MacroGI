import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Explicitly point to your .env.local file
load_dotenv()

url: str = os.getenv("URL")
key: str = os.getenv("KEY")

print(url,key)

db: Client = create_client(url, key)

