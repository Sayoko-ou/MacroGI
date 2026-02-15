"""Flask frontend for MacroGI — diabetic management web application."""
import logging
import urllib.parse
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timedelta, timezone
import random
import requests
import os
from dotenv import load_dotenv
import subprocess

# all imports from backend
from database import db
import json
from modules.fooddiary_query import query_db
from modules.dashboard_query import get_overall_data, get_weekly_data, get_daily_data

logger = logging.getLogger(__name__)

load_dotenv()

# --- Constants ---
CALENDAR_DAYS = 7           # Number of days shown in calendar strips
MAX_DASHBOARD_DAYS = 90     # Maximum days for dashboard overall view

bot = None
try:
    from modules.chatbot import MacroGIBot
    bot = MacroGIBot()
    logger.info("Real AI Chatbot Connected")
except Exception as e:
    logger.warning("Chatbot Error: %s", e)
    logger.info("Switching to Mock Chatbot (Safe Mode)")
    class MockBot:
        def get_advice(self, user_text):
            return "System: Offline."
    bot = MockBot()

app = Flask(__name__,
            template_folder="templates",
            static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))

# --- BACKEND API CONFIG ---
# In Docker, the backend service is reachable by its service name "backend"
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# --- DATABASE CONFIG ---
CLOUD_DB_URL = os.getenv("URL")
DB_KEY = os.getenv("KEY")

database_headers = {
    "apikey": DB_KEY,
    "Authorization": "Bearer " + str(DB_KEY),
    "Content-Type": "application/json",
}

# =====================================================================
# AUTH HELPERS
# =====================================================================

def is_logged_in():
    """Check whether the current session has an authenticated user."""
    return 'user_id' in session

def get_greeting():
    """Return a time-of-day greeting string."""
    current_hour = datetime.now().hour
    return "Good Morning" if 5 <= current_hour < 12 else "Good Afternoon" if 12 <= current_hour < 18 else "Good Evening"

# =====================================================================
# AUTH ROUTES
# =====================================================================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Render login form or authenticate user on POST."""
    if is_logged_in(): return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Query Cloud DB (URL-encode user input to prevent injection)
            safe_email = urllib.parse.quote(email, safe='')
            query_url = f"{CLOUD_DB_URL}/rest/v1/users_by_email?email=eq.{safe_email}&limit=1"
            response = requests.get(query_url, headers=database_headers)
            response.raise_for_status()
            users = response.json()

            if users:
                user_obj = users[0]
                # SECURITY TODO: passwords are stored and compared in plaintext.
                # This should be replaced with bcrypt hashing + DB migration.
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
            logger.error("LOGIN ERROR: %s", e)
            flash(f"Database error: {e}")

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for('login_page'))

# =====================================================================
# PAGE ROUTES
# =====================================================================

@app.route('/')
def home():
    """Render the home page with calendar and KPI data."""
    if not is_logged_in(): return redirect(url_for('login_page'))
    greeting = get_greeting()

    # Calendar Logic
    date_str = request.args.get('date')
    selected_date = datetime.now().date()
    if date_str:
        try: selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError: pass

    dates = []
    today = datetime.now().date()
    for i in range(CALENDAR_DAYS - 1, -1, -1):
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
    """Render the food scanner page."""
    if not is_logged_in(): return redirect(url_for('login_page'))
    return render_template('scan.html')

@app.route('/dashboard')
def dashboard_page():
    """Render the dashboard with overall/weekly/daily views."""
    if not is_logged_in(): return redirect(url_for('login_page'))

    greeting = get_greeting()
    view = request.args.get('view', 'overall')

    # Generate weeks: 5 weeks around selected week (arrows move between weeks)
    today = datetime.now().date()
    days_since_monday = today.weekday()
    this_week_monday = today - timedelta(days=days_since_monday)
    week_start_param = request.args.get('week_start')
    selected_week_monday = this_week_monday
    if week_start_param and view == 'weekly':
        try:
            selected_week_monday = datetime.strptime(week_start_param, '%Y-%m-%d').date()
            # Normalize to Monday
            selected_week_monday = selected_week_monday - timedelta(days=selected_week_monday.weekday())
            # Clamp to current week max: no future weeks (no data to show)
            if selected_week_monday > this_week_monday:
                selected_week_monday = this_week_monday
        except ValueError:
            selected_week_monday = this_week_monday
    # Week window: center (default), start (selected first), end (selected last)
    week_window = request.args.get('week_window', 'center')
    if week_window == 'start':
        week_offsets = range(0, 5)   # selected, +1, +2, +3, +4 weeks
    elif week_window == 'end':
        week_offsets = range(-4, 1)  # -4..0 so selected is last
    else:
        week_offsets = range(-2, 3) # 2 before, selected, 2 after
    weeks = []
    for i in week_offsets:
        week_start = selected_week_monday + timedelta(days=i * 7)
        # Only include weeks up to and including current week (no future weeks - no data yet)
        if week_start > this_week_monday:
            continue
        week_end = week_start + timedelta(days=6)
        week_num_label = week_start.isocalendar()[1]
        weeks.append({
            'week_num': week_num_label,
            'start_date': week_start.strftime('%m/%d'),
            'end_date': week_end.strftime('%m/%d'),
            'start_iso': week_start.strftime('%Y-%m-%d'),
            'end_iso': week_end.strftime('%Y-%m-%d'),
            'is_selected': week_start == selected_week_monday
        })
    # Fill white space: if we filtered future weeks, add more past weeks so we show 5
    target_count = 5
    while len(weeks) < target_count and weeks:
        earliest_start = datetime.strptime(weeks[0]['start_iso'], '%Y-%m-%d').date()
        one_earlier = earliest_start - timedelta(days=7)
        week_end = one_earlier + timedelta(days=6)
        weeks.insert(0, {
            'week_num': one_earlier.isocalendar()[1],
            'start_date': one_earlier.strftime('%m/%d'),
            'end_date': week_end.strftime('%m/%d'),
            'start_iso': one_earlier.strftime('%Y-%m-%d'),
            'end_iso': week_end.strftime('%Y-%m-%d'),
            'is_selected': one_earlier == selected_week_monday
        })

    # Generate days: center (default), start (selected first), end (selected last)
    date_str = request.args.get('date')
    selected_date = today
    if date_str and view == 'daily':
        try:
            parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
            # Clamp to today max: no future dates (no data to show yet)
            selected_date = min(parsed, today)
        except ValueError:
            selected_date = today

    day_window = request.args.get('day_window', 'center')
    if day_window == 'start':
        day_offsets = range(0, 7)    # selected, +1, ..., +6
    elif day_window == 'end':
        day_offsets = range(-6, 1)   # -6..0 so selected is last
    else:
        day_offsets = range(-3, 4)  # 3 before, selected, 3 after

    days = []
    base_date = selected_date if view == 'daily' else today
    for i in day_offsets:
        d = base_date + timedelta(days=i)
        # Only include today and past days (no future days - no data yet)
        if d > today:
            continue
        days.append({
            'day_name': d.strftime('%a').upper(),
            'day_num': d.day,
            'date_str': d.strftime('%Y-%m-%d'),
            'is_selected': d == selected_date if view == 'daily' else (d == today)
        })
    # Fill white space: if we filtered future days, add more past days so we show 7
    day_target = 7
    while len(days) < day_target and days:
        earliest = datetime.strptime(days[0]['date_str'], '%Y-%m-%d').date()
        one_earlier = earliest - timedelta(days=1)
        days.insert(0, {
            'day_name': one_earlier.strftime('%a').upper(),
            'day_num': one_earlier.day,
            'date_str': one_earlier.strftime('%Y-%m-%d'),
            'is_selected': one_earlier == selected_date if view == 'daily' else (one_earlier == today)
        })

    # Fetch data from Supabase (uses URL/KEY from .env)
    user_id = session.get('user_id')
    weekly_data = {'glycaemic_load': 0, 'carbohydrates': 0, 'calories': 0}
    daily_data = {'glycaemic_load': 0, 'carbohydrates': 0, 'calories': 0, 'food_entries': []}

    try:
        # Weekly: selected week (from week_start param or current week)
        weekly_start = selected_week_monday
        weekly_end = weekly_start + timedelta(days=6)
        weekly_data = get_weekly_data(user_id, weekly_start, weekly_end)
        # Daily: selected date
        daily_data = get_daily_data(user_id, selected_date)
    except Exception as e:
        logger.error("Dashboard initial load error: %s", e)

    # Month/year label for weekly or daily view (same box as Dashboard / Person Analytics)
    period_month_year = ''
    if view == 'weekly':
        period_month_year = selected_week_monday.strftime('%B %Y')
    elif view == 'daily':
        period_month_year = selected_date.strftime('%B %Y')

    return render_template('dashboard.html',
                         greeting=greeting,
                         user=session.get('user_name'),
                         view=view,
                         weeks=weeks,
                         days=days,
                         weekly_data=weekly_data,
                         daily_data=daily_data,
                         period_month_year=period_month_year)



@app.route('/personal-analytics')
def personal_analytics_page():
    """Render the personal analytics page with glucose trends."""
    if not is_logged_in(): return redirect(url_for('login_page'))

    greeting = get_greeting()
    view = request.args.get('view', 'overall')

    # Generate weeks (last 7 weeks)
    today = datetime.now().date()
    weeks = []
    for i in range(CALENDAR_DAYS - 1, -1, -1):
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

    return render_template('personal_analytics.html',
                         greeting=greeting,
                         user=session.get('user_name'),
                         view=view,
                         weeks=weeks,
                         days=days,
                         weekly_data=weekly_data,
                         daily_data=daily_data)


# =====================================================================
# SCANNER API ROUTES
# =====================================================================

@app.route('/scan/ocr', methods=['POST'])
def api_ocr_sim():
    """Proxy OCR request to FastAPI backend, with offline fallback."""
    if 'file' not in request.files: return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']

    try:
        files_to_send = {'file': (file.filename, file.read(), file.mimetype)}
        response = requests.post(f"{BACKEND_URL}/scan-food", files=files_to_send)
        if response.status_code == 200: return jsonify(response.json())
        else: return jsonify({"error": f"FastAPI Error: {response.text}"}), 500
    except requests.exceptions.ConnectionError:
        logger.warning("FastAPI Offline. Using Fallback.")
        # FALLBACK: Using Calories
        return jsonify({
            "nutrients": {
                "Calories": 999, "Carbohydrate": 999, "Fiber": 999,
                "Protein": 999, "Total Fat": 999, "Sodium": 999
            },
            "suggested_name": "Simulation (Offline)"
        })

@app.route('/scan/predict_gi', methods=['POST'])
def api_predict_gi_sim():
    """Proxy GI prediction request to FastAPI backend."""
    data = request.json
    data['user_id'] = session.get('user_id')
    try:
        response = requests.post(f"{BACKEND_URL}/analyze-food", json=data, timeout=3)
        if response.status_code == 200:
            return jsonify(response.json())
    except requests.exceptions.ConnectionError as e:
        logger.error("Backend connection error: %s", e)

    return jsonify({"error": "Backend unavailable"}), 503


@app.route('/scan/auto-isf-icr')
def api_auto_isf_icr():
    """Fetch auto-calculated ISF and ICR for the current user."""
    if not session.get('user_id'):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/auto-isf-icr?user_id={session['user_id']}", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
    except requests.exceptions.ConnectionError:
        pass
    return jsonify({"isf": 50, "icr": 10, "tdd": None, "source": "default"})

@app.route('/scan/insulin-advice', methods=['POST'])
def api_insulin_advice():
    """Proxy insulin advice request to FastAPI backend."""
    if not session.get('user_id'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    data['user_id'] = session['user_id']
    try:
        response = requests.post(f"{BACKEND_URL}/api/insulin-advice", json=data, timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
    except requests.exceptions.ConnectionError:
        pass
    return jsonify({"error": "Insulin advisor unavailable"}), 503

@app.route('/api/glucose-stats')
def api_glucose_stats():
    """Proxy glucose stats request to FastAPI backend."""
    user_id = request.args.get('user_id')
    try:
        response = requests.get(f"{BACKEND_URL}/api/glucose-stats?user_id={user_id}", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
    except requests.exceptions.ConnectionError:
        pass
    return jsonify({"error": "Glucose stats unavailable"}), 503

@app.route('/scan/save_entry', methods=['POST'])
def api_save_entry_sim():
    """Save a food diary entry to Supabase."""
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

        logger.info("SAVED for User %s: %s", user_id, insert_data['foodname'])

        return jsonify({
            "status": "success",
            "message": f"Successfully saved to {insert_data['mealtype']} diary!",
            "created_at": timestamp
        })

    except Exception as e:
        logger.error("DATABASE ERROR: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500

# =====================================================================
# ADVISOR API
# =====================================================================

@app.route("/advisor", methods=["POST"])
def get_response():
    """Forward user message to AI chatbot and return response."""
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Call your Gemini bot
    bot_reply = bot.get_advice(user_message)

    return jsonify({"reply": bot_reply})

# =====================================================================
# DASHBOARD API ENDPOINTS (Supabase via .env URL/KEY)
# =====================================================================

@app.route('/api/dashboard/overall', methods=['GET'])
def api_overall_data():
    """Return aggregated overall dashboard data."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    user_id = session.get('user_id')
    days = request.args.get('days', 30, type=int)
    try:
        data = get_overall_data(user_id, days=min(days, MAX_DASHBOARD_DAYS))
        return jsonify(data)
    except Exception as e:
        logger.error("Dashboard overall error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/dashboard/weekly', methods=['GET'])
def api_weekly_data():
    """Return aggregated weekly dashboard data."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    user_id = session.get('user_id')
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        start_str = week_start.strftime('%Y-%m-%d')
        end_str = week_end.strftime('%Y-%m-%d')
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d')
        data = get_weekly_data(user_id, start_date, end_date)
        return jsonify(data)
    except ValueError as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400
    except Exception as e:
        logger.error("Dashboard weekly error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/dashboard/daily', methods=['GET'])
def api_daily_data():
    """Return aggregated daily dashboard data."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    user_id = session.get('user_id')
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now().date().strftime('%Y-%m-%d')
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        data = get_daily_data(user_id, target_date)
        return jsonify(data)
    except ValueError as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400
    except Exception as e:
        logger.error("Dashboard daily error: %s", e)
        return jsonify({"error": str(e)}), 500


# =====================================================================
# FOOD DIARY
# =====================================================================

@app.route('/food-diary')
def food_diary():
    """Render the food diary page with filtering and pagination."""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('login_page'))

    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Capture filters
    food_name = request.args.get('food', '')
    time_filter = request.args.get('time', 'all')
    gi_filter = request.args.get('gi', 'all').lower()
    gi_max = request.args.get('gi_max', '100') # Added default '100'
    meal_type = request.args.get('meal', 'all').lower()
    sort_option = request.args.get('sort', 'newest')

    # 1. Base Parameters
    params = {
        'user_id': f'eq.{current_user_id}',
        'select': '*',
        'limit': per_page,
        'offset': (page - 1) * per_page
    }

    # 2. Dynamic Sorting
    if sort_option == 'oldest':
        params['order'] = 'created_at.asc'
    elif sort_option == 'highest_gi':
        params['order'] = 'gi.desc'
    else:
        params['order'] = 'created_at.desc'

    # 3. Time Filtering
    if time_filter != 'all':
        now = datetime.now(timezone.utc)
        if time_filter == '24h':
            start_date = now - timedelta(hours=24)
        elif time_filter == '7d':
            start_date = now - timedelta(days=7)
        elif time_filter == '30d':
            start_date = now - timedelta(days=30)
        params['created_at'] = f'gte.{start_date.isoformat()}'

    # 4. Food Name Search (URL-encode to prevent PostgREST injection)
    if food_name:
        safe_food_name = urllib.parse.quote(food_name, safe='')
        params['foodname'] = f'ilike.*{safe_food_name}*'

    # 5. GI Logic (Hybrid)
    if gi_filter != 'all' and gi_filter != 'custom':
        if gi_filter == 'low':
            params['gi'] = 'lte.55'
        elif gi_filter == 'medium':
            params['gi'] = 'and(gt.55,lt.70)'
        elif gi_filter == 'high':
            params['gi'] = 'gte.70'
    elif gi_max:
        safe_gi_max = urllib.parse.quote(gi_max, safe='')
        params['gi'] = f'lte.{safe_gi_max}'

    # 6. Meal Type
    if meal_type != 'all':
        params['mealtype'] = f'eq.{meal_type.capitalize()}'

    try:
        entries, total_records = query_db('meal_data', params)

        for entry in entries:
            raw_ts = entry.get('created_at')
            if raw_ts:
                dt_obj = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                entry['display_date'] = dt_obj.strftime('%d %b %Y')
                entry['display_time'] = dt_obj.strftime('%I:%M %p')

        total_pages = (total_records // per_page) + (1 if total_records % per_page > 0 else 0)
        pagination = {
            'page': page,
            'pages': max(total_pages, 1),
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1,
            'next_num': page + 1
        }

        # Create a copy of the URL parameters and remove the page key
        url_params = request.args.to_dict()
        url_params.pop('page', None)

        return render_template('food_diary.html',
                            entries=entries,
                            pagination=pagination,
                            current_sort=sort_option,
                            current_meal=meal_type,
                            current_time=time_filter,
                            url_params=url_params)

    except Exception as e:
        logger.error("Route Error: %s", e)
        return "Internal Server Error", 500


@app.route('/api/nutrients/<int:entry_id>')
def get_nutrients(entry_id):
    """Return nutrient breakdown for a specific food diary entry."""
    user_id = session.get('user_id')
    params = {
        'id': f'eq.{entry_id}',
        'user_id': f'eq.{user_id}',
        'select': '*'
    }

    try:
        data, _ = query_db('meal_data', params)
        if not data:
            return jsonify({"nutrients": []}), 404

        meal = data[0]

        nutrients_list = [
            {"name": "Calories", "value": meal.get('calories'), "unit": "kcal"},
            {"name": "Carbohydrates", "value": meal.get('carbs'), "unit": "g"},
            {"name": "Protein", "value": meal.get('protein'), "unit": "g"},
            {"name": "Fat", "value": meal.get('fat'), "unit": "g"},
            {"name": "Fiber", "value": meal.get('fiber'), "unit": "g"},
            {"name": "Sodium", "value": meal.get('sodium'), "unit": "mg"}
        ]

        return jsonify({"nutrients": nutrients_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

if __name__ == '__main__':

    is_production = os.getenv("FLASK_ENV") == "production"

    if is_production:
        # In production (Docker), each service runs in its own container.
        # Docker Compose starts the backend separately — no subprocess needed.
        logger.info("Starting Flask Frontend on port 5000 (production)...")
        app.run(host="0.0.0.0", port=5000, use_reloader=False)
    else:
        # In development, start both services from one process for convenience.
        logger.info("Starting FastAPI Backend on port 8000...")
        backend_process = subprocess.Popen(
            ["uvicorn", "fastapi_backend:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
            shell=True
        )

        try:
            logger.info("Starting Flask Frontend on port 5000...")
            app.run(debug=True, port=5000, use_reloader=False)
        finally:
            logger.info("Shutting down backend...")
            backend_process.terminate()
