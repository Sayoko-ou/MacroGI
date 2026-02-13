from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timedelta
import random
import requests
import time
import os
from dotenv import load_dotenv
from app_backend.database import db

load_dotenv()

bot = None
try:
    from app_backend.modules.chatbot import MacroGIBot
    bot = MacroGIBot()
    print("✅ Real AI Chatbot Connected")
except Exception as e:
    print(f"⚠️ Chatbot Error: {e}")
    print("ℹ️ Switching to Mock Chatbot (Safe Mode)")
    class MockBot:
        def get_advice(self, user_text):
            return "System: Offline."
    bot = MockBot()

app = Flask(__name__,
            template_folder="app_frontend/templates",
            static_folder="app_frontend/static")
app.secret_key = os.urandom(24)

# --- DATABASE CONFIG ---
CLOUD_DB_URL = os.getenv("URL")
DB_KEY = os.getenv("KEY")

database_headers = {
    "apikey": DB_KEY,
    "Authorization": "Bearer " + str(DB_KEY),
    "Content-Type": "application/json",
}

# --- LOGIN HELPER ---
def is_logged_in():
    return 'user_id' in session

def get_greeting():
    h = datetime.now().hour
    return "Good Morning" if 5 <= h < 12 else "Good Afternoon" if 12 <= h < 18 else "Good Evening"

# --- ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if is_logged_in(): return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Query Cloud DB
            query_url = f"{CLOUD_DB_URL}/rest/v1/users_by_email?email=eq.{email}&limit=1"
            response = requests.get(query_url, headers=database_headers)
            response.raise_for_status()
            users = response.json()

            if users:
                user_obj = users[0]
                if user_obj['password'] == password:
                    session['user_id'] = str(user_obj['id'])
                    session['user_name'] = user_obj['name']
                    session['user_email'] = user_obj['email']
                    return redirect(url_for('home'))
                else:
                    flash("Incorrect password")
            else:
                flash("User not found")
        except Exception as e:
            print("LOGIN ERROR:", e)
            flash(f"Database error: {e}")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
def home():
    if not is_logged_in(): return redirect(url_for('login_page'))
    greeting = get_greeting()
    
    # Calendar Logic
    date_str = request.args.get('date')
    selected_date = datetime.now().date()
    if date_str:
        try: selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except: pass

    dates = []
    today = datetime.now().date() 
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        dates.append({
            'str': d.strftime('%Y-%m-%d'),
            'day_name': d.strftime('%a'),
            'day_num': d.day,
            'is_selected': d == selected_date 
        })

    # KPI Simulation
    random.seed(selected_date.toordinal())
    gi_val = random.randint(40, 75)
    gi_color = '#28a745' if gi_val < 55 else '#ffc107' if gi_val < 70 else '#dc3545'
    
    kpi_data = {
        'calories': random.randint(1200, 2500), 
        'sugar': random.randint(20, 80), 
        'gi': gi_val, 
        'gi_color': gi_color
    }
    
    return render_template('index.html', greeting=greeting, user=session.get('user_name'), kpi=kpi_data, dates=dates)

@app.route('/scan')
def scan_page():
    if not is_logged_in(): return redirect(url_for('login_page'))
    return render_template('scan.html')

@app.route('/dashboard')
def dashboard_page():
    if not is_logged_in(): return redirect(url_for('login_page'))
    
    greeting = get_greeting()
    view = request.args.get('view', 'overall')
    
    # Generate weeks (last 7 weeks)
    today = datetime.now().date()
    weeks = []
    for i in range(6, -1, -1):
        # Calculate week start (Monday)
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday + (i * 7))
        week_end = week_start + timedelta(days=6)
        weeks.append({
            'week_num': 7 - i,
            'start_date': week_start.strftime('%m/%d'),
            'end_date': week_end.strftime('%m/%d'),
            'is_selected': i == 0
        })
    
    # Generate days (last 7 days)
    # Check if a specific date was requested for daily view
    date_str = request.args.get('date')
    selected_date = today
    if date_str and view == 'daily':
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    
    days = []
    # Show 7 days centered around selected date (or today)
    base_date = selected_date if view == 'daily' else today
    for i in range(-3, 4):  # 3 days before, selected day, 3 days after
        d = base_date + timedelta(days=i)
        days.append({
            'day_name': d.strftime('%a').upper(),
            'day_num': d.day,
            'date_str': d.strftime('%Y-%m-%d'),
            'is_selected': d == selected_date if view == 'daily' else (d == today)
        })
    
    # Generate sample data based on selected date
    date_for_seed = selected_date if view == 'daily' else today
    # Use selected_date for daily view, today for weekly/overall
    random.seed(date_for_seed.toordinal())
    
    weekly_data = {
        'glycaemic_load': random.randint(600, 800),
        'carbohydrates': random.randint(800, 1200),
        'calories': random.randint(8000, 12000)
    }
    
    daily_data = {
        'glycaemic_load': random.randint(80, 120),
        'carbohydrates': random.randint(100, 200),
        'calories': random.randint(1200, 2500),
        'food_entries': [
            {'time': '09:00', 'food': 'Bread', 'gl': 100},
            {'time': '12:00', 'food': 'McDonalds', 'gl': 400},
            {'time': '19:00', 'food': 'Snacks', 'gl': 100}
        ]
    }
    
    return render_template('dashboard.html',
                         greeting=greeting,
                         user=session.get('user_name'),
                         view=view,
                         weeks=weeks,
                         days=days,
                         weekly_data=weekly_data,
                         daily_data=daily_data)


# --- NEW API ROUTES (Simulating Microservices) ---
# --- API ROUTES ---

@app.route('/scan/ocr', methods=['POST'])
def api_ocr_sim():
    if 'file' not in request.files: return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    
    try:
        files_to_send = {'file': (file.filename, file.read(), file.mimetype)}
        response = requests.post("http://127.0.0.1:8000/scan-food", files=files_to_send)
        if response.status_code == 200: return jsonify(response.json())
        else: return jsonify({"error": f"FastAPI Error: {response.text}"}), 500
    except requests.exceptions.ConnectionError:
        print("⚠️ FastAPI Offline. Using Fallback.")
        # FALLBACK: Using Calories
        return jsonify({
            "nutrients": {
                "Calories": 250, "Carbohydrate": 32.5, "Fiber": 4.5, 
                "Protein": 8.0, "Total Fat": 10.2, "Sodium": 150
            },
            "suggested_name": "Simulation (Offline)"
        })

@app.route('/scan/predict_gi', methods=['POST'])
def api_predict_gi_sim():
    data = request.json
    try:
        response = requests.post("http://127.0.0.1:8000/analyze-food", json=data, timeout=3)
        if response.status_code == 200: return jsonify(response.json())
    except requests.exceptions.ConnectionError:
        pass

    # FALLBACK: No sugar dependency
    return jsonify({
        "gi": 55, "gl": 12, "gi_color": "#ffc107", "ai_message": "Simulation: Offline."
    })

@app.route('/scan/save_entry', methods=['POST'])
def api_save_entry_sim():
    # 1. Auth Check (Ensure this returns JSON for API calls)
    if not session.get('user_id'):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "error": "No data provided"}), 400

        # 2. Sanitize and provide defaults
        # Using .get(key, default) prevents KeyErrors
        user_id = session['user_id']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        insert_data = {
            "user_id": user_id,
            "foodname": data.get('foodname', 'Unknown Food'),
            "mealtype": data.get('mealtype', 'Other'),
            "calories": data.get('calories', 0),
            "carbs": data.get('carbs', 0),
            "protein": data.get('protein', 0),
            "fat": data.get('fat', 0),
            "fiber": data.get('fiber', 0),
            "sodium": data.get('sodium', 0),
            "insulin": data.get('insulin', 0),
            "gi": data.get('gi', 0),
            "gl": data.get('gl', 0),
            "created_at": timestamp
        }

        # 3. Database Execution
        # Use the sanitized insert_data dict here
        db.table("meal_data").insert(insert_data).execute()
        
        print(f"✅ SAVED for User {user_id}: {insert_data['foodname']}")
        
        return jsonify({
            "status": "success", 
            "message": f"Successfully saved to {insert_data['mealtype']} diary!",
            "created_at": timestamp
        })

    except Exception as e:
        print(f"❌ DATABASE ERROR: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/advisor", methods=["POST"])
def get_response():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Call your Gemini bot
    bot_reply = bot.get_advice(user_message)
    
    return jsonify({"reply": bot_reply})

# Dashboard API Endpoints
@app.route('/api/dashboard/weekly', methods=['GET'])
def api_weekly_data():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    
    week = request.args.get('week', '1')
    random.seed(int(week) * 1000)
    
    return jsonify({
        'glycaemic_load': random.randint(600, 800),
        'carbohydrates': random.randint(800, 1200),
        'calories': random.randint(8000, 12000)
    })
    if not user_message: return jsonify({"error": "No message"}), 400
    return jsonify({"reply": bot.get_advice(user_message)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)