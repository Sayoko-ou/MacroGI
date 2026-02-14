# MacroGI Dashboard: UI/UX Principles, Model Integration & Advanced Features

**Report and presentation support document for the MacroGI Applied AI project.**

---

## 1. Dashboard Overview

The MacroGI dashboard is the central analytics hub where users view their nutrition and glycaemic data over time. It is designed to support **three distinct temporal granularities** so users can zoom from high-level trends down to individual meals.

| View | Purpose | Key Metrics & Visualizations |
|------|---------|------------------------------|
| **Overall** | Long-term patterns (e.g. last 30 days) | Monthly trends (line), meal-type distribution by GL (pie), Top 20 highest-GI foods and carbs (bar charts) |
| **Weekly** | Week-at-a-glance for planning and reflection | Summary cards (GL, Carbs, Calories), weekly trends line chart, Top 5 highest-GL foods, meal distribution pie, daily breakdown bar chart |
| **Daily** | Single-day detail and food log | Summary cards, chronological food log (timeline), daily trends chart |

The dashboard is **API-driven**: data is fetched from a backend that aggregates from **Supabase** (`meal_data` table), so the same pipeline that stores scan results powers all visualizations. This keeps a single source of truth and ensures the UI always reflects the latest saved entries.

---

## 2. UI/UX Principles Applied

The interface is designed to be **proficient, intuitive, and coherent** across the whole solution. Below are the main UX principles applied and how they show up in the dashboard and app.

### 2.1 Consistency & Coherence

- **Design system**: A small set of CSS variables (`--nav-blue`, `--highlight-blue`, `--text-dark`, `--text-grey`, `--bg-color`, `--white`) is used across the app (navbar, dashboard, scan, food diary, buttons). This creates a **consistent visual language** and makes the product feel like one product, not separate pages.
- **Navigation**: The same top navbar (Home, Scanner, Dashboard, Food Diary) appears on every page. The dashboard itself uses a secondary nav (DASHBOARD vs PERSON ANALYTICS) and a **view selector** (Overall / Weekly / Daily) so users always know where they are and how to switch context.
- **Components**: Buttons (view buttons, week/day buttons, nav arrows), cards (summary cards, chart cards), and typography (headings, labels) reuse the same styles so interactions behave and look the same everywhere.

### 2.2 Progressive Disclosure & Contextual Controls

- **Relevant controls only**: The week selector (with arrows and week chips) is shown **only in Weekly view**; the day selector is shown **only in Daily view**. In Overall view, no date strip is shown. This avoids clutter and makes it clear which control affects which view.
- **Clear affordances**: Arrows (← / →) are explicitly “previous/next period.” Week and day chips show date ranges or day names and numbers so users can **see the current selection** and choose another without guessing.

### 2.3 Feedback & Responsiveness

- **Active states**: The selected view (Overall/Weekly/Daily) and the selected week or day are clearly highlighted (e.g. blue background, white text). This gives **immediate feedback** on the current context.
- **Data refresh**: The dashboard refreshes the active view from the API on a timer (e.g. every 60 seconds), so new entries (e.g. from the scanner or food diary) appear without a manual reload. After date navigation (arrows or chip click), data is loaded for the new period so the user always sees up-to-date numbers and charts.

### 2.4 Hierarchy & Scannability

- **Summary at the top**: In Weekly and Daily views, **summary cards** (Glycaemic Load, Carbohydrates, Calories) appear first. Users get the main numbers quickly; charts provide detail below.
- **Chart labels**: Each chart has a clear heading (e.g. “Weekly Trends”, “Daily Breakdown”, “Top 5 Highest GL food”). Axis labels and legends (e.g. Carb vs GL vs Calories) are used so charts are interpretable at a glance.

### 2.5 Flexibility & Efficiency

- **Temporal navigation**: Users can move between weeks (Weekly) or days (Daily) via **arrows** (next/previous period) or by **clicking a week/day chip**. The URL updates (e.g. `?view=weekly&week_start=YYYY-MM-DD` or `?view=daily&date=YYYY-MM-DD`), so the same view can be bookmarked or shared.
- **Larger charts on screen**: Chart containers use flexible heights (e.g. `min-height`, `45vh`) so Weekly and Daily views **use more of the viewport**, reducing scrolling and making trends easier to read.

### 2.6 Accessibility & Readability

- **Typography**: A single, readable font (Inter) with clear weight hierarchy (e.g. 800 for headings, 700 for labels) is used across the app.
- **Color**: Contrast between text and background is maintained; the same blue palette is used for primary actions and selection so the interface is consistent and not overly noisy.

### 2.7 Responsive Behaviour

- **Breakpoints**: Layout adapts for smaller screens (e.g. chart sections and weekly/daily grids stack vertically, summary cards and date selectors reflow) so the dashboard remains usable on different devices.

Together, these choices make the dashboard **easy to learn** (familiar patterns, clear labels), **efficient to use** (quick period change, visible summaries), and **aligned with the rest of MacroGI** (same colours, nav, and interaction patterns).

---

## 3. Model Integration in the Solution

MacroGI integrates **multiple models and AI components** into one pipeline. The dashboard does not run models directly; it **displays outcomes** of that pipeline (GI, GL, and meal data stored in Supabase). Below is how each model fits and how it is showcased.

### 3.1 Glycaemic Index (GI) Prediction Model

- **Technology**: Random Forest regressor (e.g. scikit-learn), loaded from `best_random_forest_model.pkl`.
- **Inputs**: Nutrient features (e.g. Sugar, Fiber, Carbohydrate, Fat, Protein, Sodium) in the order expected by the model (`feature_names.pkl`).
- **Output**: Predicted GI value per food/meal.
- **Where it runs**: In the **FastAPI backend** (`/analyze-food`). The Flask app sends scan/OCR nutrients to FastAPI; FastAPI calls `predict_gi_sklearn(nutrients)` and returns GI (and derived GL) to the frontend.
- **How it’s showcased**: 
  - **Scanner**: User sees predicted GI (and often a colour cue, e.g. green/amber/red) and GL after scanning or entering food.
  - **Food Diary / Supabase**: When the user saves a meal, GI/GL (and related fields) are stored in `meal_data`.
  - **Dashboard**: All views aggregate **GL, carbs, and calories** from `meal_data`; the “Top GI/GL foods” and trends are direct reflections of the model’s predictions over time.

**Benefit**: Users get a **consistent, data-driven GI estimate** for every logged item, which powers both real-time feedback (scan) and historical analytics (dashboard).

### 3.2 Glycaemic Load (GL) Calculation

- **Formula**: \( \text{GL} = (\text{GI} \times \text{carbs}) / 100 \).
- **Uses**: Output of the GI model plus carbohydrate amount. GL is stored with each meal and is the main metric shown in dashboard summaries and charts (e.g. “Glycaemic Load” cards and “Daily Breakdown” by GL).

**Benefit**: Combines **portion size (carbs)** with **quality (GI)** so the dashboard reflects both what they ate and how glycaemic it is.

### 3.3 Insulin Suggestion Logic

- **Technology**: Rule-based / heuristic model (optionally backed by a dedicated model later) that uses **carbs and GI** to suggest insulin units (e.g. base on carbs, adjusted by GI band).
- **Where it runs**: FastAPI `analyze-food` pipeline, after GI prediction.
- **How it’s showcased**: Scanner (and any scan-result UI) can show the suggested insulin amount alongside GI/GL, making the **end-to-end flow** (scan → GI → GL → insulin suggestion) visible.

**Benefit**: Connects **nutrition data and AI-predicted GI** to a concrete action (insulin dosing), demonstrating applied value for diabetic management.

### 3.4 GenAI Advisor (LLM)

- **Technology**: LLM (e.g. Llama 3.1 or similar via Hugging Face) used to generate short, personalised **health tips** based on food name, nutrients, and predicted GI/GL.
- **Where it runs**: FastAPI, after GI/GL are computed; tip is returned in the same API response as GI, GL, and insulin.
- **How it’s showcased**: Scanner shows the AI tip next to the metrics; the **MacroGI Advisor** chatbot (e.g. Gemini) elsewhere in the app provides conversational support.

**Benefit**: Users get **explainable, contextual advice** tied to the same numbers they see in the dashboard, improving understanding and trust.

### 3.5 Table Detection / OCR Pipeline

- **Technology**: Optional **table-detection model** (e.g. Keras) to crop the nutrition facts panel before OCR, improving extraction accuracy.
- **Where it runs**: In the scan/OCR pipeline (e.g. FastAPI or shared backend) before nutrient parsing.
- **How it’s showcased**: Better **accuracy of scanned nutrients** → better GI/GL predictions → more reliable dashboard data.

**Benefit**: Shows how **computer vision** supports the rest of the pipeline and ultimately the quality of dashboard analytics.

---

## 4. Advanced Features (Clear Explanations & Benefits)

| Feature | What it does | Benefit |
|--------|----------------|---------|
| **Three temporal views** | Overall (e.g. 30 days), Weekly (one week), Daily (one day) with dedicated charts and KPIs for each. | Users can switch between “big picture” and “detail” without leaving the dashboard; supports different tasks (e.g. monthly review vs daily planning). |
| **Week and day navigation** | Arrows move to previous/next week or day; week/day chips let users jump to a specific period. URL params (`week_start`, `date`) keep state. | Efficient navigation and shareable/bookmarkable links; no need to reload and hunt for the right week/day. |
| **API-driven charts** | All chart data comes from REST endpoints that query Supabase (e.g. `/api/dashboard/overall`, `/weekly`, `/daily`). | Single source of truth (Supabase); dashboard stays in sync with scanner and food diary; easy to add caching or new data sources later. |
| **Auto-refresh** | The active view is refetched on a timer (e.g. every 60 seconds). | Newly logged meals appear in the dashboard without manual refresh; good for multi-device or shared use. |
| **Summary cards** | In Weekly and Daily views, GL, Carbs, and Calories are shown in large cards at the top. | Key numbers are visible immediately; charts add detail for those who want it. |
| **Chart.js visualizations** | Line charts (trends), bar charts (breakdowns, top foods), pie charts (meal-type distribution) with consistent colours and legends. | Data is easy to compare and interpret; the same chart patterns are reused across views for consistency. |
| **Responsive layout** | Grids and date selectors reflow on smaller screens; chart height uses viewport-relative units where appropriate. | Usable on desktop and mobile; better use of screen space. |
| **Contextual date controls** | Week selector only in Weekly view; day selector only in Daily view; period label (e.g. month/year) updates with selection. | Reduces cognitive load and avoids irrelevant controls. |

These features are **directly tied to the data produced by the models** (GI/GL and stored meals), so the dashboard effectively showcases the **end-to-end value** of the applied AI solution.

---

## 5. Coherence Across the Solution

- **Single design system**: Colours, type, buttons, and cards are shared across Dashboard, Scanner, Food Diary, and base layout. The dashboard does not introduce a second “theme.”
- **Unified data flow**: Scanner (and food diary) → FastAPI (GI/GL/insulin/tips) → Supabase (`meal_data`) → Dashboard APIs → Charts. The same metrics (GI, GL, carbs, calories) appear in scan results, diary, and dashboard.
- **Unified navigation**: One navbar; dashboard has its own sub-nav and view/date controls. Users can move between “log food” (scan/diary) and “review” (dashboard) without learning a new structure.
- **Consistent terminology**: Terms like “Glycaemic Load,” “Carbohydrates,” “Calories,” “Meal type” are used the same way in UI labels, tooltips, and charts.

This coherence makes the product feel **intentional and professional** and supports the narrative that the dashboard is the **analytics face** of the same AI and data pipeline used everywhere else.

---

## 6. Additional Points for Report and Presentation

### 6.1 Architecture

- **Flask** (frontend routes, session, proxy to FastAPI); **FastAPI** (OCR, GI model, GL, insulin, GenAI); **Supabase** (persistent meal data); **Chart.js** (client-side charts). You can describe this as a **multi-tier, API-driven** design that separates UI, business logic, and data.

### 6.2 Data Pipeline

- Scan/OCR → nutrients → FastAPI → GI model + GL + insulin + GenAI → response to frontend; optional save to Supabase → dashboard aggregates from Supabase. Emphasise **one pipeline, multiple touchpoints** (real-time scan vs historical dashboard).

### 6.3 Scalability and Maintainability

- Dashboard does not duplicate aggregation logic; it calls APIs. Adding a new chart or view usually means a new endpoint and front-end chart config. Models (Random Forest, insulin rules, GenAI) are in separate modules so they can be updated or A/B tested independently.

### 6.4 Possible Future Work

- Person-level analytics (PERSON ANALYTICS tab), more granular filters (e.g. by meal type in Overall), export (CSV/PDF), or goals/alerts based on GL/carbs. These can be mentioned as natural extensions of the current UX and data model.

### 6.5 Ethical and Practical Considerations

- **Medical disclaimer**: The chatbot (and any AI advice) should be framed as educational only, not replacing clinical advice—good to mention in the report.
- **Data privacy**: User-scoped data (e.g. `user_id` in `meal_data`) and secure API access support privacy and multi-user scenarios.

---

## 7. Summary

The MacroGI dashboard is built to be **proficient and intuitive**, following **consistency, progressive disclosure, feedback, hierarchy, and responsiveness**. It **showcases the integrated solution** by visualising the same GI/GL and meal data produced by the **Random Forest GI model**, **GL formula**, **insulin logic**, and **GenAI advisor**, all stored in Supabase and exposed through a **coherent, API-driven UI**. Emphasising these design choices, model roles, and advanced features in your report and presentation will clearly demonstrate both the **UX quality** and the **end-to-end applied AI** value of the project.
