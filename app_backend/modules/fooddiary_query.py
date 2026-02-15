"""Food diary database query helper for Supabase/PostgREST."""
import logging
from dotenv import load_dotenv
import os
import requests

logger = logging.getLogger(__name__)

load_dotenv()

CLOUD_DB_URL = os.getenv("URL")
DB_KEY = os.getenv("KEY")

database_headers = {
    "apikey": DB_KEY,
    "Authorization": "Bearer " + str(DB_KEY),
    "Content-Type": "application/json",
}


def query_db(table, params=None):
    """Enhanced helper to fetch data from Supabase/PostgREST."""
    url = f"{CLOUD_DB_URL}/rest/v1/{table}"

    # Add 'Prefer' header to get the total row count for pagination
    headers = database_headers.copy()
    headers["Prefer"] = "count=exact"

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            try:
                error_info = response.json()
                logger.warning("DB error: %s - %s", error_info.get('message'), error_info.get('hint'))
            except Exception:
                logger.warning("DB error: Status %s", response.status_code)

        response.raise_for_status()

        # Return both the data and the total count from the headers
        content_range = response.headers.get("Content-Range", "0-0/0")
        total_count = int(content_range.split("/")[-1])

        return response.json(), total_count

    except requests.exceptions.HTTPError as err:
        logger.error("HTTP Error occurred: %s", err)
        return [], 0
    except Exception as err:
        logger.error("An unexpected error occurred: %s", err)
        return [], 0
