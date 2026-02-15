"""
Dashboard data aggregation from Supabase (meal_data table).
Uses URL and KEY from .env for Supabase connection.
"""
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from app_backend.modules.fooddiary_query import query_db

logger = logging.getLogger(__name__)


def _parse_created_at(entry):
    """Parse created_at from entry, return datetime (naive UTC) or None."""
    raw = entry.get('created_at')
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        # Normalize to naive UTC for comparison (avoids offset-naive vs offset-aware errors)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_month_sort(s):
    """Sort key for month strings like 'Jan 24' or 'Dec 23'."""
    try:
        if s and len(s.split()) == 2:
            return datetime.strptime(s, '%b %y')
        return datetime.min
    except (ValueError, IndexError):
        return datetime.min


def _safe_float(val, default=0):
    """Safely convert a value to float, returning default on failure."""
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def get_overall_data(user_id, days=30):
    """Aggregate meal_data for overall dashboard (last N days)."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_str = start.strftime('%Y-%m-%dT%H:%M:%S')
    end_str = end.strftime('%Y-%m-%dT%H:%M:%S')

    params = {
        'user_id': f'eq.{user_id}',
        'select': 'foodname,mealtype,calories,carbs,gl,gi,created_at',
        'order': 'created_at.asc',
        'created_at': f'gte.{start_str}',
        'limit': 5000,
    }
    # PostgREST: add second filter via or - we use gte and fetch, then filter in Python
    entries, _ = query_db('meal_data', params)
    entries = [e for e in entries if _parse_created_at(e) and _parse_created_at(e) <= end.replace(tzinfo=None)]

    # Aggregate by month
    monthly = defaultdict(lambda: {'calories': 0, 'carbs': 0, 'gl': 0})
    meal_gl = defaultdict(float)
    food_gi = []
    food_carb = []

    for entry in entries:
        dt = _parse_created_at(entry)
        if not dt:
            continue
        month_key = dt.strftime('%b %y')
        cal = _safe_float(entry.get('calories'))
        carbs = _safe_float(entry.get('carbs'))
        gl = _safe_float(entry.get('gl'))
        gi = _safe_float(entry.get('gi'))
        meal = (entry.get('mealtype') or 'Other').capitalize()

        monthly[month_key]['calories'] += cal
        monthly[month_key]['carbs'] += carbs
        monthly[month_key]['gl'] += gl
        meal_gl[meal] += gl
        food_gi.append({'name': entry.get('foodname') or 'Unknown', 'gi': gi})
        food_carb.append({'name': entry.get('foodname') or 'Unknown', 'carbs': carbs})

    # Sort months chronologically (last 7 months)
    sorted_months = sorted(monthly.keys(), key=lambda m: _parse_month_sort(m))
    sorted_months = sorted_months[-7:] if len(sorted_months) > 7 else sorted_months

    line_data = {
        'labels': sorted_months,
        'carb': [monthly[m]['carbs'] for m in sorted_months],
        'gl': [monthly[m]['gl'] for m in sorted_months],
        'calories': [monthly[m]['calories'] for m in sorted_months],
    }
    pie_data = {
        'labels': list(meal_gl.keys()),
        'values': list(meal_gl.values()),
    }
    top_gi = sorted(food_gi, key=lambda x: x['gi'], reverse=True)[:20]
    top_carb = sorted(food_carb, key=lambda x: x['carbs'], reverse=True)[:20]

    return {
        'line_chart': line_data,
        'pie_chart': pie_data,
        'top_gi': top_gi,
        'top_carb': top_carb,
    }


def get_weekly_data(user_id, start_date, end_date):
    """Aggregate meal_data for weekly view."""
    start_str = start_date.strftime('%Y-%m-%dT00:00:00')
    end_str = end_date.strftime('%Y-%m-%dT23:59:59')

    params = {
        'user_id': f'eq.{user_id}',
        'select': 'foodname,mealtype,calories,carbs,gl,gi,created_at',
        'order': 'created_at.asc',
        'created_at': f'gte.{start_str}',
        'limit': 5000,
    }
    entries, _ = query_db('meal_data', params)
    end_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S')
    entries = [e for e in entries if _parse_created_at(e) and _parse_created_at(e) <= end_dt]

    daily = defaultdict(lambda: {'calories': 0, 'carbs': 0, 'gl': 0})
    food_gl = defaultdict(float)
    meal_counts = defaultdict(float)

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily[d.strftime('%a')] = {'calories': 0, 'carbs': 0, 'gl': 0}

    for entry in entries:
        dt = _parse_created_at(entry)
        if not dt or dt.date() < start_date.date() or dt.date() > end_date.date():
            continue
        day_key = dt.strftime('%a')
        cal = _safe_float(entry.get('calories'))
        carbs = _safe_float(entry.get('carbs'))
        gl = _safe_float(entry.get('gl'))
        meal = (entry.get('mealtype') or 'Other').capitalize()
        food_gl[entry.get('foodname') or 'Unknown'] += gl
        meal_counts[meal] += gl
        if day_key in daily:
            daily[day_key]['calories'] += cal
            daily[day_key]['carbs'] += carbs
            daily[day_key]['gl'] += gl

    total_gl = sum(d['gl'] for d in daily.values())
    total_carbs = sum(d['carbs'] for d in daily.values())
    total_cal = sum(d['calories'] for d in daily.values())

    ordered = [daily[d] for d in day_names if d in daily]
    if not ordered:
        ordered = [{'calories': 0, 'carbs': 0, 'gl': 0}] * 7

    top5_gl = sorted(food_gl.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        'glycaemic_load': round(total_gl),
        'carbohydrates': round(total_carbs),
        'calories': round(total_cal),
        'line_labels': day_names,
        'line_carb': [daily[d]['carbs'] for d in day_names],
        'line_gl': [daily[d]['gl'] for d in day_names],
        'line_calories': [daily[d]['calories'] for d in day_names],
        'daily_breakdown_gl': [daily[d]['gl'] for d in day_names],
        'daily_breakdown_carbs': [daily[d]['carbs'] for d in day_names],
        'daily_breakdown_calories': [daily[d]['calories'] for d in day_names],
        'top5_gl': [{'name': n, 'gl': round(v)} for n, v in top5_gl],
        'pie_labels': list(meal_counts.keys()),
        'pie_values': list(meal_counts.values()),
    }


def get_daily_data(user_id, target_date):
    """Aggregate meal_data for a single day."""
    start_str = target_date.strftime('%Y-%m-%dT00:00:00')
    end_str = target_date.strftime('%Y-%m-%dT23:59:59')

    params = {
        'user_id': f'eq.{user_id}',
        'select': 'foodname,mealtype,calories,carbs,gl,gi,created_at',
        'order': 'created_at.asc',
        'created_at': f'gte.{start_str}',
        'limit': 500,
    }
    entries, _ = query_db('meal_data', params)
    end_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S')
    entries = [entry for entry in entries if _parse_created_at(entry) and _parse_created_at(entry) <= end_dt]

    food_entries = []
    total_gl = total_carbs = total_cal = 0

    for entry in entries:
        dt = _parse_created_at(entry)
        if not dt:
            continue
        cal = _safe_float(entry.get('calories'))
        carbs = _safe_float(entry.get('carbs'))
        gl = _safe_float(entry.get('gl'))
        total_gl += gl
        total_carbs += carbs
        total_cal += cal
        food_entries.append({
            'time': dt.strftime('%H:%M'),
            'food': entry.get('foodname') or 'Unknown',
            'gl': round(gl),
        })

    # Line chart data (by entry time)
    labels = [fe['time'] for fe in food_entries]
    carb_vals = [_safe_float(entry.get('carbs')) for entry in entries]
    gl_vals = [_safe_float(entry.get('gl')) for entry in entries]
    cal_vals = [_safe_float(entry.get('calories')) for entry in entries]

    if not labels:
        labels = ['--']
        carb_vals = gl_vals = cal_vals = [0]

    return {
        'glycaemic_load': round(total_gl),
        'carbohydrates': round(total_carbs),
        'calories': round(total_cal),
        'food_entries': food_entries,
        'line_labels': labels,
        'line_carb': carb_vals,
        'line_gl': gl_vals,
        'line_calories': cal_vals,
    }
