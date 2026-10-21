# ReviewPulse: step-by-step guide

This guide takes you from "I have a zip file" to "this project is on my resume, deployed, and I can defend it in any interview".

> **Golden rule:** interviewers *will* ask "walk me through your code". Plan about 7 days to read, run and modify every file before you put this on your resume. A project you can't explain hurts you more than having no project.

---

## Why this project (and how it complements your resume)

| Your current projects show | ReviewPulse adds |
|---|---|
| MERN full-stack, RBAC, REST APIs | **Python backend** (FastAPI), **SQL analytics** (window functions, CTEs) |
| Computer vision / deep learning | **NLP** on text plus honest **model evaluation** (precision/recall) |
| Deployment on Render | **Docker, CI/CD (GitHub Actions), automated tests** |
| — | **Business thinking:** KPIs, insights, recommended actions, stakeholder exports |

That last row is why it works for **non-technical roles** (Business Analyst, Data Analyst, Product Analyst, consulting, operations). Those interviewers don't care about FastAPI; they care that you found *"iOS complaints rose 450% after a release"* and recommended a rollback.

---

## Step 1: Install the tools (about 30 min)
1. **Python 3.11 or newer**: python.org → Download. On Windows, tick **"Add Python to PATH"**.
2. **Git** (you already use it) and **VS Code** with the *Python* extension.
3. *(Optional)* **Docker Desktop**, only needed for the PostgreSQL version.

Check in a terminal:
```bash
python --version     # 3.11+
git --version
```

## Step 2: Run it locally (about 10 min)
Unzip `reviewpulse.zip`, open the folder in VS Code, open the terminal (Ctrl + `):

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```
Open **http://localhost:8000**. The dashboard loads with 2,558 demo reviews. Also open **http://localhost:8000/docs** for the auto-generated API docs, which are great to show in interviews.

Try these:
- Click **Hyderabad** in the Cities table → every chart filters.
- Click the red **App Experience** bar → the explorer shows those complaints.
- Tick **"Stars ≠ text only"** → see 5-star reviews that are actually complaints.
- Click **Export CSV**.

Then run the other tools:
```bash
pytest -q                              # 19 tests should pass
python scripts/run_sql.py              # 7 SQL business questions + results
python scripts/evaluate_sentiment.py   # accuracy, precision, recall
```

## Step 3: Understand the code (days 1–5)
Read the files **in this order**. Each one is short and commented.

| Day | File | What to learn | Self-check question |
|---|---|---|---|
| 1 | `scripts/generate_data.py` | How the demo data is built and the **3 hidden problems** in it | What are the 3 planted problems, and from which week? |
| 1 | `app/database.py`, `app/models.py` | SQLAlchemy ORM, one-to-many design, indexes | Why is `review_topics` a separate table and not a column? |
| 2 | `app/nlp.py` | VADER sentiment, compound score thresholds, regex topic rules | Why does "delivery fee" not count as a Delivery topic? |
| 2 | `app/ingest.py` | ETL: validate → transform → load, batch commits | What happens to a row with rating 9? |
| 3 | `app/analytics.py` | Parameterised SQL, `CASE WHEN` aggregation | Why can't `column` be a bound parameter, and how is it protected? |
| 3 | `sql/analytics_queries.sql` | CTE, `LAG`, `RANK`, `ROW_NUMBER`, rolling window | Rewrite Q3 without window functions |
| 4 | `app/insights.py` | Window comparison (4 vs 4 weeks), thresholds, LLM fallback | Why `MIN_RECENT = 8`? What would go wrong with 1? |
| 4 | `app/main.py` | FastAPI routes, dependency injection, validation, upload limits | What does `Depends(get_db)` do? |
| 5 | `app/static/app.js` | `fetch` API calls, Chart.js, state, debounced search | Why is there a 300 ms `setTimeout` on search? |
| 5 | `tests/`, `.github/workflows/ci.yml`, `Dockerfile` | Testing, CI pipeline, containers | What happens on GitHub when you push? |

**Tip:** for each file, explain it out loud in 2 sentences as if to an interviewer. If you can't, re-read it.

## Step 4: Make it yours (day 6). Don't skip this.
A copied project is easy to spot. Make **at least two** real changes and commit them separately:
- Add a new topic (for example "Hygiene": `dirty`, `hair`, `unhygienic`) in `nlp.py` and add a test for it.
- Add a KPI tile (for example "% neutral").
- Add a date-range filter to the dashboard (backend `_where()` + frontend).
- Change the demo company or industry (for example e-commerce reviews instead of food).
- Add a new SQL question to `sql/analytics_queries.sql`.

## Step 5: Push to GitHub
Create an empty repo named `reviewpulse` on GitHub (no README), then:
```bash
git init
git add .
git commit -m "Initial ReviewPulse: ingestion, NLP, analytics API, dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/reviewpulse.git
git push -u origin main
```
Commit your Step 4 changes as **separate commits over several days**. A healthy commit history looks real; one giant commit doesn't.

The **Actions** tab will show CI running lint, tests, SQL and the Docker build. A green tick on your repo is a nice signal.

## Step 6: Deploy on Render (free)
1. render.com → **New → Web Service** → connect your GitHub repo.
2. Render detects Python. Set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Environment variable: `PYTHON_VERSION` = `3.12.7`
3. Deploy, then open the URL. Paste it into the README ("Live demo") and onto your resume.

Note: on the free plan the app sleeps when idle (the first load takes about 30–50 s), and the SQLite file resets on each deploy. The demo data reloads automatically, so this is fine for a portfolio.

## Step 7 (optional): Turn on the AI executive summary
1. Get a free Gemini API key at **aistudio.google.com/apikey**.
2. Locally: `set LLM_API_KEY=your_key` (Windows) or `export LLM_API_KEY=your_key`, then restart uvicorn.
   On Render: add `LLM_API_KEY` under *Environment*.
3. The summary box label changes from "rule-based" to "AI-generated".

Any OpenAI-compatible provider works; change `LLM_API_BASE` and `LLM_MODEL` (see `.env.example`). If the API fails, the app falls back to rule-based text, so the dashboard never breaks.

## Step 8 (recommended): Analyse real data
The demo data is synthetic, so say so if asked. To strengthen the project, find a public review dataset on Kaggle (search "food delivery app reviews" or "Play Store reviews"), rename its columns to `review_text`, `rating`, `date` (plus `city`/`platform` if available), and upload it with **Upload CSV → Replace existing data**. Then write 3–4 real findings in your README. *"I analysed 10,000 real Play Store reviews and found…"* is a very strong interview line.

---

## Step 9: Put it on your resume
Put ReviewPulse **first** in Projects. It's your most complete project.

**Version A: software / AI / technical roles**
> **ReviewPulse – Customer Feedback Analytics Platform** | GitHub | Live Demo
> *Python, FastAPI, SQL (PostgreSQL), Pandas, NLP, Chart.js, Docker, GitHub Actions*
> - Built an end-to-end platform that ingests customer reviews via a validated ETL pipeline, classifies sentiment and 7 complaint topics, and serves KPIs (CSAT, % negative, weekly trends) through a REST API and interactive dashboard.
> - Designed an insights engine comparing rolling 4-week windows to flag emerging problems with recommended actions; on a 2,500-review dataset it automatically detected an iOS release issue (+450% complaints) and a city-level delivery crisis.
> - Wrote analytical SQL (CTEs, window functions), reached 84% sentiment agreement with star ratings, and shipped with 19 automated tests, Docker and CI/CD.

**Version B: analyst / product / consulting / non-technical roles**
> **ReviewPulse – Customer Feedback Analytics Dashboard** | GitHub | Live Demo
> *SQL, Python, Pandas, Data Visualisation, NLP*
> - Analysed 2,500+ customer reviews to find the drivers of dissatisfaction by city and platform; delivery issues appeared in 24% of negative reviews.
> - Built a self-serve dashboard with KPIs (CSAT, rating trend, complaint share) and automated weekly insights, each with a recommended business action.
> - Found that ~10% of reviews had star ratings that contradicted their text, showing that star ratings alone understate customer dissatisfaction.

Add to **Skills**: `FastAPI`, `SQLAlchemy`, `PostgreSQL`, `Pandas`, `Docker`, `GitHub Actions (CI/CD)`, `pytest`, `Data Visualisation (Chart.js)`.

---

## Step 10: Interview preparation (day 7)

### Your 60-second pitch
> "Companies get thousands of reviews but managers only look at the average rating, which hides *why* customers are unhappy. I built ReviewPulse, which takes raw reviews, works out the sentiment and the topic of each complaint, stores them in SQL and shows a dashboard. The key part is an insights engine that compares the last four weeks with the four before and says, in plain English, what is getting worse and what to do. For example, it flagged that iOS app complaints went up 450% after a release and recommended a rollback. It's built with FastAPI, SQL and Chart.js, has 19 tests and CI, and is deployed on Render."

**Analogy for non-technical interviewers:** *"It's like a doctor reading thousands of patient notes overnight and telling the hospital head each morning: 'fever cases are up 3× in Ward B, check the water supply.'"*

### Technical questions
| Question | Answer outline |
|---|---|
| Why VADER and not BERT? | Fast, needs no GPU or training data, explainable. I added a domain lexicon and measured 84% agreement. Trade-off: it misses negation like "got no help". Next step: fine-tune DistilBERT on labelled reviews. |
| How did you measure accuracy without labels? | Used stars as weak labels (4–5 positive, 1–2 negative, 3 excluded). Reported precision and recall, not just accuracy. Negative recall (78%) is the weak spot. |
| Why a separate `review_topics` table? | One review can have several topics (one-to-many). A comma-separated column breaks normalisation and makes `GROUP BY topic` hard. |
| How do you prevent SQL injection? | All values are bound parameters (`:city`). Column names can't be parameters, so they're checked against a whitelist. There's a test that sends `'; DROP TABLE` in the search box. |
| How do you avoid false alarms in insights? | Minimum volume threshold (8 recent mentions), equal-length windows, and one insight per topic so one root cause isn't reported 5 times. Improvement: a significance test (chi-square / two-proportion z-test). |
| How would it scale to 10 million reviews? | Background job queue for ingestion (Celery/RQ), batch inserts, PostgreSQL with indexes (already on city, platform, week, sentiment), pre-aggregated daily summary tables, caching for dashboard queries. |
| What does your CI do? | On every push: lint (Ruff), run 19 tests, run the SQL file, build the Docker image. A broken commit shows a red cross. |
| What if the LLM API is down? | Caught in try/except with a timeout, and the app falls back to rule-based text, so the dashboard never breaks. The prompt tells the model to use only the given facts, which reduces hallucination. |
| Explain `LAG` / `ROW_NUMBER` in your SQL. | LAG reads the previous week's value to compute week-over-week change. ROW_NUMBER partitioned by city ranks complaints inside each city to get the top 2 per city. |

### Non-technical / HR questions (answer in STAR format)
- **"Tell me about a project you're proud of."** Situation (reviews ignored) → Task (find the why) → Action (pipeline, insights engine) → Result (detected 3 problems automatically, with actions).
- **"Who is the user and what decision does it help with?"** An operations or product manager deciding where to spend effort this week: which city, which team, which fix.
- **"How would you measure if this tool is successful?"** Time to detect a problem (days → hours), CSAT improvement after acting on insights, and how many managers use it weekly.
- **"What's CSAT vs NPS?"** CSAT = % of satisfied responses (here 4–5★). NPS = % promoters (9–10) − % detractors (0–6) on a "would you recommend" scale.
- **"A trade-off you made?"** I chose explainable rule-based topics over a black-box model because business users need to trust *why* a review was tagged. Accuracy is lower, but adoption is higher.
- **"What would you do differently?"** Use real data from the start, add statistical significance testing, and get feedback from a real manager on which insights matter.

---

## Extensions (if you have more time)
- Date-range filter and week-over-week KPI deltas on the tiles
- Login with roles (reuse your RBAC skills from the Faculty Workload project)
- Scheduled weekly email report of insights
- Replace VADER with a Hugging Face transformer and compare accuracy in a table
- "Ask your data" box: natural language → SQL using the LLM (with read-only DB user)

## Project structure
```
reviewpulse/
├── app/
│   ├── main.py          # FastAPI routes
│   ├── database.py      # DB connection (SQLite / PostgreSQL)
│   ├── models.py        # Review, ReviewTopic tables
│   ├── ingest.py        # CSV → validate → NLP → SQL
│   ├── nlp.py           # sentiment + topic detection
│   ├── analytics.py     # KPI SQL queries
│   ├── insights.py      # insights engine + LLM summary
│   └── static/          # dashboard (HTML, CSS, JS)
├── data/sample_reviews.csv
├── sql/analytics_queries.sql
├── scripts/             # generate_data, run_sql, evaluate_sentiment
├── tests/               # 19 pytest tests
├── Dockerfile, docker-compose.yml, render.yaml
└── .github/workflows/ci.yml
```
