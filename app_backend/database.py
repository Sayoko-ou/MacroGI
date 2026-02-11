# NOTE: THIS FILE IS MEANT TO STORE ALL VARIABLES THAT WILL BE USED TO CONNECT TO CLOUD DB CLUSTER

from pymongo import MongoClient
import sys
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DATABASE_NAME")

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    user_diary = db.user_diary

except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    sys.exit(1)