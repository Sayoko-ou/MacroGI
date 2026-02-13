from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timedelta
import random
import requests
import time
import os



bot = None
try:
    from app_backend.modules.chatbot import MacroGIBot
    # If this succeeds, we create the real bot
    bot = MacroGIBot()
    print("✅ Real AI Chatbot Connected")

except Exception as e:
    print(f"⚠️ Chatbot Error: {e}")
    print("ℹ️ Switching to Mock Chatbot (Safe Mode)")

    class MockBot:
        def get_advice(self, user_text):
            return "System: I am currently offline because the API Key is missing. Please ask Jing En to send the .env file."
    
    bot = MockBot()


app = Flask(__name__,
            template_folder="app_frontend/templates",
            static_folder="app_frontend/static")
app.secret_key = os.urandom(24)

# --- 1. UPDATED USER DATABASE (With IDs) ---
# Format: Email is key -> Value is dict with details
USERS = {
    "alex@macrogi.com": {
        "password": "password123",
        "name": "Alex",
        "id": "1" 
    },
    "judge@school.com": {
        "password": "admin",
        "name": "Judge",
        "id": "0"
    }
}

# --- LOGIN HELPER ---
def is_logged_in():
    return 'user_id' in session

    
# --- Existing Helper Functions ---
def get_greeting():
    h = datetime.now().hour
    return "Good Morning" if 5 <= h < 12 else "Good Afternoon" if 12 <= h < 18 else "Good Evening"

# --- PAGE ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    # If already logged in, skip login page
    if is_logged_in():
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 1. Check if email exists in our dict
        if email in USERS:
            user_obj = USERS[email]
            
            # 2. Check password match
            if user_obj['password'] == password:
                # 3. Save User ID and Name to Cookie
                session['user_id'] = user_obj['id']
                session['user_name'] = user_obj['name']
                session['user_email'] = email
                return redirect(url_for('home'))
            else:
                flash("Incorrect password")
        else:
            flash("User not found")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() # This kills the cookie
    return redirect(url_for('login_page'))
    

@app.route('/')
def home():
    if not is_logged_in(): return redirect(url_for('login_page'))

    greeting = get_greeting()
    
    # --- 1. GET DATE FROM URL ---
    # Check if user clicked a specific date (e.g. /?date=2026-02-10)
    date_str = request.args.get('date')
    
    if date_str:
        try:
            # Convert string "2026-02-10" -> Date Object
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            # If someone messes with URL, fallback to today
            selected_date = datetime.now().date()
    else:
        # Default to today
        selected_date = datetime.now().date()

    # --- 2. GENERATE CALENDAR STRIP ---
    # We always show the *last 7 days* ending on today
    today = datetime.now().date() 
    dates = []
    
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        dates.append({
            'str': d.strftime('%Y-%m-%d'),
            'day_name': d.strftime('%a'),
            'day_num': d.day,
            # Highlight if this day matches the one we selected
            'is_selected': d == selected_date 
        })

    # --- 3. GENERATE DATA FOR SELECTED DATE ---
    # Use the selected date as the "Seed" so the numbers are consistent for that day
    # (e.g. Feb 10 always shows the same numbers, Feb 9 shows different ones)
    random.seed(selected_date.toordinal())
    
    gi_val = random.randint(40, 75)
    gi_color = '#28a745' if gi_val < 55 else '#ffc107' if gi_val < 70 else '#dc3545'
    
    kpi_data = {
        'calories': random.randint(1200, 2500), 
        'sugar': random.randint(20, 80), 
        'gi': gi_val, 
        'gi_color': gi_color
    }
    
    return render_template('index.html', 
                         greeting=greeting, 
                         user=session.get('user_name'),
                         kpi=kpi_data, 
                         dates=dates)
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
    
    # 1. TRY CONNECTING TO FASTAPI 
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



# app.py

@app.route('/scan/save_entry', methods=['POST'])
def api_save_entry_sim():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    
    # Inject Database Metadata
    # Note: 'created_at' replaces 'timestamp' to match your schema
    final_entry = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": session['user_id'],
        "foodname": data.get('foodname'),
        "mealtype": data.get('mealtype'),
        "carbs": data.get('carbs', 0),
        "protein": data.get('protein', 0),
        "fat": data.get('fat', 0),
        "fiber": data.get('fiber', 0),
        "sodium": data.get('sodium', 0),
        "insulin": data.get('insulin', 0)
    }
    
    # GI is not in your list of 10 columns, so we omit it from storage
    print(f"DATABASE INSERT: {final_entry}") 
    
    return jsonify({
        "status": "success", 
        "message": f"Successfully saved to {final_entry['mealtype']} diary!",
        "created_at": final_entry['created_at']
    })



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