from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timedelta
import random
import requests
import time # Needed for simulated delays
from app_backend.modules.chatbot import MacroGIBot

app = Flask(__name__,
            template_folder="app_frontend/templates",
            static_folder="app_frontend/static")
app.secret_key = "applied_ai_project"

# --- SIMPLE USER DATABASE (No MongoDB needed) ---
# Format: "email": "password"
USERS = {
    "alex@macrogi.com": "password123",
    "judge@school.com": "admin"
}

# --- LOGIN HELPER ---
def is_logged_in():
    return 'user_email' in session

    
# --- Existing Helper Functions ---
def get_greeting():
    h = datetime.now().hour
    return "Good Morning" if 5 <= h < 12 else "Good Afternoon" if 12 <= h < 18 else "Good Evening"

# --- PAGE ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check against our simple dictionary
        if email in USERS and USERS[email] == password:
            session['user_email'] = email
            session['user_name'] = email.split('@')[0].capitalize() # "Alex"
            return redirect(url_for('home'))
        else:
            flash("Invalid email or password")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() # Deletes the cookie
    return redirect(url_for('login_page'))
    

@app.route('/')
def home():
    if not is_logged_in(): return redirect(url_for('login_page'))
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
    
    return render_template('index.html', greeting=get_greeting(), user=session['user_name'], dates=dates, kpi=kpi_data)

@app.route('/scan')
def scan_page():
    if not is_logged_in(): return redirect(url_for('login_page'))
    return render_template('scan.html')


# --- NEW API ROUTES (Simulating Microservices) ---

@app.route('/scan/ocr', methods=['POST'])
def api_ocr_sim():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    
    # 1. TRY CONNECTING TO FASTAPI (The Real Way)
    try:
        # Prepare the file to send to Port 8000
        # We need to send it as 'multipart/form-data'
        files_to_send = {'file': (file.filename, file.read(), file.mimetype)}
        
        # Send to the FastAPI endpoint defined in ai_service.py
        response = requests.post("http://127.0.0.1:8000/scan-food", files=files_to_send)
        
        if response.status_code == 200:
            print("✅ OCR Success via FastAPI")
            return jsonify(response.json())
        else:
            return jsonify({"error": f"FastAPI Error: {response.text}"}), 500
            
    except requests.exceptions.ConnectionError:
        print("⚠️ FastAPI (OCR) is offline. Using Simulation Data.")

    # 2. FALLBACK (Only runs if you forgot to start the second terminal)
    fake_ocr_data = {
        "nutrients": {
            "carbs": 32.5, "sugar": 12.0, "fiber": 4.5, 
            "protein": 8.0, "fat": 10.2, "sodium": 150
        },
        "suggested_name": "Simulation (Server Offline)"
    }
    return jsonify(fake_ocr_data)


@app.route('/scan/predict_gi', methods=['POST'])
def api_predict_gi_sim():
    data = request.json
    
    # 1. TRY CONNECTING TO FASTAPI (The Real Way)
    try:
        # Assuming FastAPI is running on Port 8000
        response = requests.post("http://127.0.0.1:8000/analyze-food", json=data, timeout=3)
        
        if response.status_code == 200:
            print("✅ Connected to FastAPI Backend!")
            return jsonify(response.json())
        else:
            print(f"⚠️ FastAPI Error: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️ FastAPI is offline. Using Simulation Data.")

    # 2. FALLBACK SIMULATION (If FastAPI is down or not implemented yet)
    # This keeps your frontend working no matter what
    try:
        sugar = float(data['nutrients'].get('sugar', 0))
        fiber = float(data['nutrients'].get('fiber', 1))
        
        base_gi = 50 + (sugar * 1.5) - (fiber * 2)
        final_gi = int(max(10, min(100, base_gi)))
        
        gi_color = '#28a745'
        if final_gi >= 55: gi_color = '#ffc107'
        if final_gi >= 70: gi_color = '#dc3545'

        return jsonify({
            "gi": final_gi, 
            "gi_color": gi_color, 
            "ai_message": "Simulation: High fiber helps reduce glucose spikes."
        })
    except:
        return jsonify({"error": "Invalid data"}), 400


## Use this when implementing
#@app.route('/scan/predict_gi', methods=['POST'])
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



@app.route('/scan/save_entry', methods=['POST'])
def api_save_entry_sim():
    """Simulates saving the final validated entry to DB"""
    time.sleep(0.5)
    
    # 1. Get data from Frontend
    data = request.json
    
    # 2. INJECT TIMESTAMP (Server Time)
    # Formats as "2023-10-27 14:30:00"
    data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 3. Save to DB (or print for demo)
    # If you were using MongoDB: db.diary.insert_one(data)
    print(f"✅ SAVING TO DB (With Time): {data}") 
    
    return jsonify({
        "status": "success", 
        "message": "Entry saved to diary!",
        "saved_at": data['timestamp'] # Send it back just in case
    })


bot = MacroGIBot()

@app.route("/advisor", methods=["POST"])
def get_response():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Call your Gemini bot
    bot_reply = bot.get_advice(user_message)
    
    return jsonify({"reply": bot_reply})


if __name__ == '__main__':
    app.run(debug=True, port=5000)