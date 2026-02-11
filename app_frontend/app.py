from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import random
import time # Needed for simulated delays

app = Flask(__name__)

# --- Existing Helper Functions ---
def get_greeting():
    h = datetime.now().hour
    return "Good Morning" if 5 <= h < 12 else "Good Afternoon" if 12 <= h < 18 else "Good Evening"

# --- PAGE ROUTES ---

@app.route('/')
def home():
    # (Keep your existing home route logic exactly the same)
    # ... [Truncated for brevity, assume existing code here] ...
    # For demo purposes, re-inserting minimal needed variables if you copy-paste:
    selected_date = datetime.now().date()
    dates = []
    for i in range(6, -1, -1):
        d = datetime.now().date() - timedelta(days=i)
        dates.append({
            'str': d.strftime('%Y-%m-%d'),
            'day_name': d.strftime('%a'),
            'day_num': d.day,
            'is_selected': d == selected_date
        })
    random.seed(selected_date.toordinal())
    gi_val = random.randint(40, 75)
    gi_color = '#28a745' if gi_val < 55 else '#ffc107' if gi_val < 70 else '#dc3545'
    kpi_data = {'calories': random.randint(1200, 2500), 'sugar': random.randint(20, 80), 'gi': gi_val, 'gi_color': gi_color}
    
    return render_template('index.html', greeting=get_greeting(), dates=dates, kpi=kpi_data)

@app.route('/scan')
def scan_page():
    # Just renders the empty scan page framework
    return render_template('scan.html')


# --- NEW API ROUTES (Simulating Microservices) ---

@app.route('/api/ocr', methods=['POST'])
def api_ocr_sim():
    """Simulates recieving an image and running OCR"""
    time.sleep(1.5) # Simulate processing delay

    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    # In reality, you would send this file to your FastAPI service here.
    # For demo, we return fake detected data.
   # app.py -> api_ocr_sim

    fake_ocr_data = {
        "nutrients": {
            "carbs": 32.5,
            "sugar": 12.0,
            "fiber": 4.5,
            "protein": 8.0,
            "fat": 10.2,
            "sodium": 150  # Added sodium to test the 'mg' logic
        },
        "suggested_name": random.choice(["", "Unknown Label", "Granola Bar"])
    }
    return jsonify(fake_ocr_data)

@app.route('/api/predict_gi', methods=['POST'])
def api_predict_gi_sim():
    """Simulates taking numerical nutrient data and predicting GI"""
    time.sleep(1) # Simulate delay
    data = request.json

    # In reality, send 'data' to FastAPI GI Model.
    # Simple fake logic based on sugar/fiber ratio
    try:
        sugar = float(data.get('sugar', 0))
        fiber = float(data.get('fiber', 1)) # avoid div by zero
        
        base_gi = 50 + (sugar * 1.5) - (fiber * 2)
        final_gi = int(max(10, min(100, base_gi))) # Clamp between 10 and 100

        gi_color = '#28a745' # Green
        if final_gi >= 55: gi_color = '#ffc107' # Orange
        if final_gi >= 70: gi_color = '#dc3545' # Red

        return jsonify({"gi": final_gi, "gi_color": gi_color})

    except ValueError:
        return jsonify({"error": "Invalid numerical data"}), 400


## Use this when implementing
#@app.route('/api/predict_gi', methods=['POST'])
#def api_predict_gi_sim():
#    data = request.json # Grab data from frontend table
#    
#    # Connect to FastAPI
#    try:
#        # Note: Port 8000 is where FastAPI lives
#        response = requests.post("http://127.0.0.1:8000/analyze-food", json=data)
#        return jsonify(response.json())
#        
#    except requests.exceptions.ConnectionError:
#        return jsonify({"error": "AI Service is offline"}), 500



@app.route('/api/save_entry', methods=['POST'])
def api_save_entry_sim():
    """Simulates saving the final validated entry to DB"""
    time.sleep(0.5)
    data = request.json
    # Here you would use PyMongo to save 'data' to your database
    print(f"SAVING TO DB: {data}") 
    return jsonify({"status": "success", "message": "Entry saved to diary!"})


if __name__ == '__main__':
    app.run(debug=True, port=5000)