# MacroGI

A diabetic management web application that combines food label scanning (OCR), glycemic index prediction, blood glucose forecasting, and AI-powered dietary advice to help users manage their diabetes.

## Features

- **Food Label Scanner** — Upload a photo of a food label and extract nutritional data using OCR (RapidOCR + OpenCV). Automatically detects table layouts for improved accuracy.
- **GI/GL Prediction** — Predicts the Glycemic Index and Glycemic Load of scanned foods using a trained Random Forest model.
- **Blood Glucose Forecasting** — Predicts glucose levels at 30, 60, and 90 minutes ahead using an LSTM neural network, with per-user fine-tuning support.
- **Insulin Advisor** — Recommends insulin dosage based on current blood glucose, planned carbs, Insulin-on-Board (IOB), and auto-calculated ISF/ICR.
- **AI Chatbot** — Google Gemini-powered dietary advisor for personalized nutrition guidance.
- **Food Diary** — Tracks meals with filtering, sorting, and pagination. Logs nutritional data, GI/GL values, and insulin doses.
- **Dashboard** — Aggregated views (overall, weekly, daily) of glycemic load, calories, and carbohydrate trends.
- **Personal Analytics** — Glucose trend charts with SHAP-based model explainability.
- **CGM Simulator** — Generates synthetic continuous glucose monitor readings for testing and development.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Flask, Jinja2, HTML/CSS/JS |
| Backend API | FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL) |
| ML Models | Scikit-learn (Random Forest), TensorFlow/Keras (LSTM) |
| OCR | RapidOCR (ONNX Runtime), OpenCV |
| AI/LLM | Google Gemini, HuggingFace (Llama 3.1) |
| Explainability | SHAP |
| Deployment | Docker, Railway |
| CI/CD | GitHub Actions |

## Project Structure

```
MacroGI/
├── .github/workflows/       # CI/CD pipelines
│   ├── ci.yml                # Lint + Docker build checks
│   └── deploy.yml            # Auto-deploy to Railway
├── cgm_simulator/            # Synthetic CGM data generator
│   └── CGM_simulation.py
├── ml_training/              # Jupyter notebooks for model training
│   ├── 01_BG_Forecast_Preprocessing.ipynb
│   └── 02_BG_Forecast_Training.ipynb
├── models/                   # Pre-trained ML models
│   ├── best_random_forest_model.pkl
│   ├── bg_forecast_lstm.keras
│   ├── bg_forecast_meta.json
│   ├── bg_forecast_scaler.joblib
│   ├── feature_names.pkl
│   └── table_classifier.keras
├── modules/                  # Core application logic
│   ├── bg_explainer.py       # SHAP explainability
│   ├── bg_finetune.py        # Per-user LSTM fine-tuning
│   ├── bg_forecast.py        # Blood glucose prediction
│   ├── chatbot.py            # Google Gemini chatbot
│   ├── dashboard_query.py    # Dashboard data aggregation
│   ├── fooddiary_query.py    # Food diary database queries
│   ├── genai_advisor.py      # HuggingFace Llama food advisor
│   ├── gi_predictor.py       # GI prediction (Random Forest)
│   ├── insulin_advisor.py    # Insulin dosage recommendations
│   ├── insulin_predictor.py  # Insulin prediction logic
│   ├── knowledge_base.json   # Chatbot knowledge base
│   └── ocr_engine.py         # RapidOCR food label scanner
├── static/
│   ├── css/                  # Stylesheets (per-page)
│   ├── imgs/                 # Static images
│   └── js/                   # Frontend JavaScript (per-page)
├── templates/                # Flask HTML templates
├── database.py               # Supabase client initialization
├── fastapi_backend.py        # FastAPI backend server
├── flask_backend.py          # Flask frontend server
├── docker-compose.yml        # Multi-service orchestration
├── Dockerfile.backend        # FastAPI container
├── Dockerfile.frontend       # Flask container
└── requirements.txt          # Python dependencies
```

## Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project with the required tables (`users_by_email`, `meal_data`, `cgm_data`)
- API keys for Google Gemini and HuggingFace

## Environment Variables

Create a `.env` file in the project root:

```env
# Supabase
URL=https://your-project.supabase.co
KEY=your-supabase-anon-key

# AI Services
GEMINI_API_KEY=your-gemini-api-key
HF_TOKEN=your-huggingface-token

# Flask
SECRET_KEY=your-flask-secret-key
FLASK_ENV=development

# Backend URL (overridden by Docker Compose in production)
BACKEND_URL=http://127.0.0.1:8000
```

## Getting Started

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/MacroGI.git
   cd MacroGI
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```

3. **Set up your `.env` file** with the required environment variables (see above).

4. **Run the application:**
   ```bash
   python flask_backend.py
   ```
   This starts both the Flask frontend (port 5000) and the FastAPI backend (port 8000) in development mode.

5. **Open your browser** at `http://localhost:5000`.

### Docker

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```
   This starts two services:
   - **Frontend** (Flask) at `http://localhost:5000`
   - **Backend** (FastAPI) at `http://localhost:8000`

2. **Stop the services:**
   ```bash
   docker-compose down
   ```

## Architecture

```
┌──────────────────┐       HTTP        ┌──────────────────┐
│   Flask Frontend │  ───────────────► │  FastAPI Backend  │
│   (Port 5000)    │                   │   (Port 8000)    │
│                  │                   │                  │
│  - Auth/Sessions │                   │  - OCR Engine    │
│  - Page Routing  │                   │  - GI Prediction │
│  - Dashboard     │                   │  - BG Forecast   │
│  - Food Diary    │                   │  - Insulin Advice│
│  - Chatbot UI    │                   │  - CGM Endpoints │
└────────┬─────────┘                   └────────┬─────────┘
         │                                      │
         │              Supabase                 │
         └──────────► (PostgreSQL) ◄─────────────┘
```

- The **Flask frontend** handles authentication, page rendering, and proxies API requests to the backend.
- The **FastAPI backend** handles ML inference, OCR processing, glucose forecasting, and insulin calculations.
- Both services connect to **Supabase** for data persistence.

## ML Models

| Model | File | Purpose |
|-------|------|---------|
| Random Forest | `best_random_forest_model.pkl` | Predicts Glycemic Index from nutritional features |
| LSTM | `bg_forecast_lstm.keras` | Forecasts blood glucose at 30/60/90 min horizons |
| Table Classifier | `table_classifier.keras` | Detects nutrition table layout in food label images |
| Feature Scaler | `bg_forecast_scaler.joblib` | Normalizes input features for the LSTM model |

The LSTM model supports **per-user fine-tuning** — freezes the base LSTM layers and retrains the dense head on individual user data via the `/api/finetune-model` endpoint.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on every push to `main`/`develop` and PRs to `main`. Performs flake8 linting and Docker image build verification.
- **CD** (`.github/workflows/deploy.yml`): Automatically deploys to [Railway](https://railway.app) on pushes to `main`.

## API Endpoints

### FastAPI Backend

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/scan-food` | OCR food label image |
| POST | `/analyze-food` | Predict GI/GL + AI tip |
| POST | `/cgms-data` | Store CGM reading |
| POST | `/forecast-bg` | Forecast glucose (30/60/90 min) |
| GET | `/api/glucose-stats` | Glucose chart data + forecasts |
| POST | `/api/finetune-model` | Trigger per-user model fine-tuning |
| GET | `/api/auto-isf-icr` | Auto-calculate ISF and ICR |
| POST | `/api/insulin-advice` | Calculate recommended insulin dose |

### Flask Frontend

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/login` | Authentication |
| GET | `/logout` | Clear session |
| GET | `/` | Home page with KPIs |
| GET | `/scan` | Food scanner page |
| GET | `/dashboard` | Dashboard (overall/weekly/daily) |
| GET | `/personal-analytics` | Glucose analytics |
| GET | `/food-diary` | Food diary with filters |
| POST | `/advisor` | AI chatbot interaction |
