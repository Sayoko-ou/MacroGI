"""Supabase client initialization and helper functions."""
import logging
import os
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Explicitly point to your .env.local file
load_dotenv()

url: str = os.getenv("URL")
key: str = os.getenv("KEY")

db: Client = create_client(url, key)

