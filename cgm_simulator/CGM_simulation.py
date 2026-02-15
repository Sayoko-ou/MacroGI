import httpx
import asyncio
import time
import random
from datetime import datetime, timedelta

USER_ID = 2
# Conversion factor constant
MMOL_TO_MG_DL = 18

async def send_data(timestamp, glucose, USER_ID):
    url = "http://127.0.0.1:8000/cgms-data"
    payload = {
        'user_id': USER_ID,
        'timestamp': timestamp.isoformat(),
        'bg_value': round(glucose, 1) # Rounded for cleaner data
    }

    print(f"Sending: {payload}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            print(f"Status Code: {response.status_code}")
        except Exception as e:
            print(f"Connection failed: {e}")

def simulate_cgm_step(current_glucose, current_time):
    # 1. Random walk logic (Adjusted for mg/dL scale)
    # A 0.3 mmol/L change is roughly 5.4 mg/dL
    change = random.uniform(-5.5, 5.5) 
    
    # Drift back toward a healthy baseline of 100 mg/dL (~5.5 mmol/L)
    drift = (100 - current_glucose) * 0.1
    
    new_glucose = current_glucose + change + drift
    
    # 2. Physiological limits in mg/dL
    # 40 mg/dL (severe hypo) to 400 mg/dL (severe hyper)
    new_glucose = max(40, min(400, new_glucose))
    
    # 3. Advance time
    new_time = current_time + timedelta(minutes=5)
    
    return new_glucose, new_time

# --- INITIAL STATE (Starting at 100 mg/dL) ---
glucose = 100.0
timestamp = datetime.now()

async def main():
    global glucose, timestamp
    while True:
        # 1. Send the current state FIRST (this will be 'now' on the first run)
        await send_data(timestamp, glucose, USER_ID)

        # 2. Wait for the interval
        await asyncio.sleep(300)

        # 3. Calculate the NEXT values for the next iteration
        glucose, timestamp = simulate_cgm_step(glucose, timestamp)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Simulation stopped.")