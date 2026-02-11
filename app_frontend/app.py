from flask import Flask, render_template, request
from datetime import datetime, timedelta
import random

app = Flask(__name__)

def get_greeting():
    h = datetime.now().hour
    return "Good Morning" if 5 <= h < 12 else "Good Afternoon" if 12 <= h < 18 else "Good Evening"

@app.route('/')
def home():
    # 1. HANDLE DATE SELECTION
    # We check if the user clicked a specific date (e.g., ?date=2023-10-25)
    selected_str = request.args.get('date')
    if selected_str:
        try:
            selected_date = datetime.strptime(selected_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = datetime.now().date()
    else:
        selected_date = datetime.now().date()

    # 2. GENERATE CALENDAR STRIP (Last 7 Days)
    # This creates the list of objects that the HTML loop uses
    dates = []
    for i in range(6, -1, -1):
        d = datetime.now().date() - timedelta(days=i)
        dates.append({
            'str': d.strftime('%Y-%m-%d'),  # For the link URL
            'day_name': d.strftime('%a'),   # "Mon", "Tue"
            'day_num': d.day,               # 12, 13
            'is_selected': d == selected_date
        })

    # 3. FAKE KPI DATA (Seeded by date)
    # This ensures that if you click "Yesterday", the numbers change but stay consistent for that day
    random.seed(selected_date.toordinal())
    
    gi_val = random.randint(40, 75)
    # Logic to pick the color for the GI text
    gi_color = '#28a745' if gi_val < 55 else '#ffc107' if gi_val < 70 else '#dc3545'

    kpi_data = {
        'calories': random.randint(1200, 2500),
        'sugar': random.randint(20, 80),
        'gi': gi_val,
        'gi_color': gi_color
    }

    # 4. RENDER THE PAGE
    # passing all our calculated data to the HTML
    return render_template('index.html', 
                           greeting=get_greeting(), 
                           dates=dates, 
                           kpi=kpi_data)

@app.route('/upload', methods=['POST'])
def upload_file():
    # This is a placeholder for your future connection to FastAPI
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    return f"File {file.filename} received! (Connect FastAPI here later)"

if __name__ == '__main__':
    app.run(debug=True, port=5000)