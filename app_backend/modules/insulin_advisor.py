"""Insulin advisor: auto-calculates ISF/ICR from TDD and advises dosing."""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def calculate_tdd(db, user_id):
    """
    Calculate Total Daily Dose (TDD) from the last 7 days of meal_data.
    Returns average daily insulin, or None if insufficient data.
    """
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    response = db.table("meal_data") \
        .select("insulin, created_at") \
        .eq("user_id", user_id) \
        .gt("created_at", seven_days_ago) \
        .execute()

    rows = response.data or []
    if not rows:
        return None

    # Sum insulin per day, then average across days that have data
    daily_totals = {}
    for row in rows:
        insulin = float(row.get("insulin") or 0)
        if insulin <= 0:
            continue
        day = row["created_at"][:10]  # YYYY-MM-DD
        daily_totals[day] = daily_totals.get(day, 0.0) + insulin

    if not daily_totals:
        return None

    return sum(daily_totals.values()) / len(daily_totals)


def auto_isf_icr(db, user_id):
    """
    Auto-calculate ISF (1800 rule) and ICR (500 rule) from TDD.
    Falls back to ISF=50, ICR=10 if insufficient data.
    """
    tdd = calculate_tdd(db, user_id)

    if tdd and tdd > 0:
        isf = round(1800 / tdd, 1)
        icr = round(500 / tdd, 1)
        # Clamp to reasonable ranges
        isf = max(10, min(isf, 200))
        icr = max(3, min(icr, 50))
        return {"isf": isf, "icr": icr, "tdd": round(tdd, 1), "source": "calculated"}
    else:
        return {"isf": 50, "icr": 10, "tdd": None, "source": "default"}

def compute_iob(db, user_id):
    """
    Compute current Insulin on Board using exponential decay (75-min half-life).
    Looks back 5 hours for insulin events.
    """
    # Fix 1: Use UTC time for the lookback so it matches Supabase format
    now_utc = datetime.now(timezone.utc)
    lookback = (now_utc - timedelta(hours=5)).isoformat()

    response = db.table("meal_data") \
        .select("insulin, created_at") \
        .eq("user_id", user_id) \
        .gt("created_at", lookback) \
        .order("created_at", desc=False) \
        .execute()

    rows = response.data or []
    iob = 0.0
    half_life = 75  # minutes

    for row in rows:
        insulin = float(row.get("insulin") or 0)
        if insulin <= 0:
            continue
        
        # Fix 2: Parse the Supabase timestamp (which includes a timezone)
        event_time = datetime.fromisoformat(row["created_at"])
        
        # Calculate elapsed minutes safely using UTC
        elapsed_min = (now_utc - event_time).total_seconds() / 60
        remaining = insulin * (0.5 ** (elapsed_min / half_life))
        iob += remaining

    return round(iob, 2)


def advise_dose(current_bg, target_bg, planned_carbs, iob, isf, icr):
    """
    Calculate recommended insulin dose.
    Returns a breakdown dict with correction, meal, IOB adjustment, and total.
    """
    # Correction dose: only if BG is above target
    correction = max(0, (current_bg - target_bg) / isf)

    # Meal dose
    meal_dose = planned_carbs / icr

    # Total minus IOB, floor at 0
    raw_total = correction + meal_dose - iob
    total = max(0, raw_total)

    # Round to nearest 0.5
    total = round(total * 2) / 2

    return {
        "correction_dose": round(correction, 2),
        "meal_dose": round(meal_dose, 2),
        "iob_adjustment": round(iob, 2),
        "total_dose": total,
        "current_bg": current_bg,
        "target_bg": target_bg,
        "isf_used": isf,
        "icr_used": icr,
    }
