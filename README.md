# Brand Comment Intelligence & Ad Optimizer

A Streamlit application that collects YouTube comments about a brand and turns them into an overview of customer sentiment, common topics, buying signals, brand discovery sources, and suggested advertising budget allocation.

The app combines keyword-based analysis with two Gemini-powered AI agents:
- **Insights agent:** summarizes what people like or dislike, common questions, and possible actions for the brand.
- **Marketing agent:** recommends platforms to consider for advertising and a suggested budget split. It can use Google Search grounding when enabled.

> **Important:** Results are estimates based on publicly available YouTube videos and comments. Keyword rules can misclassify sarcasm, negation, and context. Mentions of a platform in comments are not verified traffic or sales attribution.

## Features

- Search YouTube for videos related to a brand and optional niche.
- Use the YouTube Data API when a key is configured, with a `yt-dlp` search fallback.
- Collect comments from multiple videos, sorted by popularity or recency.
- Score comments as **Positive**, **Neutral**, or **Negative** using VADER sentiment analysis.
- Categorize comments as praise, complaint, question, suggestion, bought it, wants to buy, or other.
- Identify keyword-based topics such as price, quality, design, performance, delivery, service/trust, durability/comfort, and availability.
- Scan comments for buying intent, purchase claims, show-off comments, mentioned platforms/stores, discovery cues, language, and locations.
- Run two Gemini agents concurrently for customer insights and marketing recommendations.
- Compare comment patterns across videos, sources, topics, locations, and languages.
- Set a separate advertising budget for each saved brand and view suggested allocations.
- Cluster comment patterns into interpretable groups using sentiment, purchase signals, engagement, language, topic and comment type.
- Detect statistically unusual posts using robust outlier thresholds across post and comment metrics.
- Download collected data as CSV or Excel.

## Project structure

```text
.
├── app.py                 # Main Streamlit dashboard
├── agents.py              # Gemini API calls and AI agents
├── app_links.py           # Alternate/standalone YouTube-link sentiment interface
├── brand_insights.py      # Purchase signals, source/discovery analysis, budget helpers
├── brand_pipeline.py      # Brand-to-videos-to-comments collection pipeline
├── config.py              # Reads environment variables and local .env settings
├── topics.py              # Comment types, topic keywords, and summaries
├── youtube_search.py      # YouTube Data API search and yt-dlp fallback
├── youtube_sentiment.py   # Comment cleaning, VADER sentiment, CLI analysis
├── test_keys.py           # Checks API key configuration
├── test_sdk.py            # Tests the optional official Gemini SDK
├── requirements.txt       # Python dependencies
└── .env                   # Your local API keys (create this; do not commit it)
```

## Requirements

- Python 3.10 or newer is recommended.
- Internet access.
- A Google Gemini API key for AI-generated insights and marketing recommendations.
- A YouTube Data API v3 key is optional. Without it, video search can fall back to `yt-dlp`.

## Installation

Open a terminal in the project folder and create a virtual environment.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configure API keys

Create a file named `.env` in the same folder as `app.py`. Add your keys and optional settings:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=your_youtube_data_api_key_here
GEMINI_MODEL=gemini-3.8-flash
USE_WEB_SEARCH=true
```

- Get a Gemini key from [Google AI Studio](https://aistudio.google.com/).
- Create a YouTube Data API v3 key in the [Google Cloud Console](https://console.cloud.google.com/). Enable **YouTube Data API v3** for the project if you use this key.
- `YOUTUBE_API_KEY` is optional; omit it or leave it blank to allow the `yt-dlp` fallback.
- `GEMINI_MODEL` is optional. If omitted, the app uses its configured default model and has logic to handle unavailable model names.
- `USE_WEB_SEARCH` controls whether the marketing agent may use Google Search grounding; it defaults to enabled unless set to `0`, `false`, `no`, or `off`.

Do not add real API keys to source files, screenshots, public repositories, or commit history. Add `.env` to `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
data/
```

## Run the application

From the project folder, activate the virtual environment and run:

```bash
python -m streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`. Open it in your browser.

## How to use the dashboard

1. Open **Collect comments**.
2. Enter a brand name and, optionally, its niche.
3. Choose the maximum number of videos, comments per video, and total comments to collect.
4. Choose whether to keep only videos that mention the brand name. Add video links manually if needed.
5. Start collection and review any notes or skipped videos.
6. Open **Comments & insights** to explore sentiment, comment types, topics, and discovery signals.
7. Open **Ad optimizer** to set the brand's budget and review data-based and AI-generated recommendations.
8. Open **Audience clusters** to generate comment-pattern clusters and flag unusual posts.
9. Open **Data tables** to inspect and export all saved results.

Each brand saved during the current Streamlit session has its own collected comments and budget. The app uses Streamlit session state, so this is not a permanent database; restarting the app may clear the saved in-session brand selections. CSV files are also written by the collection pipeline to the `data/` folder.

## Optional: run the YouTube-link analyzer

`youtube_sentiment.py` also provides a command-line interface for analyzing comments from one or more YouTube videos.

```bash
python youtube_sentiment.py
```

You can paste links interactively, pass links as arguments, or provide a text file containing one URL per line:

```bash
python youtube_sentiment.py "https://www.youtube.com/watch?v=VIDEO_ID"
python youtube_sentiment.py LINK1 LINK2 --limit 1000
python youtube_sentiment.py --file links.txt
```

The alternate Streamlit interface in `app_links.py` is intended for analyzing supplied YouTube links rather than searching for a brand first. Run it with:

```bash
python -m streamlit run app_links.py
```

## API key troubleshooting

Run the key checker from the project folder:

```bash
python test_keys.py
```

To test the optional official Gemini Python SDK, install it and run:

```bash
python -m pip install google-genai
python test_sdk.py
```

The current `requirements.txt` does not list `google-genai`; the main app can use direct HTTPS requests, and the SDK is an optional fallback. If a key is rejected, create or verify the key and ensure the relevant Google API is enabled. If requests time out or are rate-limited, retry later or choose an available model using `GEMINI_MODEL`.

## Analysis notes and limitations

- Sentiment is calculated with VADER, a general-purpose sentiment tool. It may not correctly understand all slang, sarcasm, mixed-language comments, or context.
- Comment types, topics, purchase claims, and discovery/source cues rely partly on keyword patterns in English and Roman Urdu. These are useful indicators, not verified facts.
- A comment saying that a person found or bought a product on a platform does not establish that the platform generated the sale.
- Comment samples are limited by the selected caps and by whether a video has accessible comments.
- AI-generated insights and budget recommendations should be reviewed by a person before making business decisions.
- Budget allocations are recommendations, not actual campaign performance forecasts.
- Do not treat comment-derived city/country or language labels as reliable demographic analytics.

## Dependencies

The main dependencies listed in `requirements.txt` are:

- Streamlit — web dashboard
- Requests — HTTP API requests
- Pandas — tabular data processing
- Matplotlib — charts
- OpenPyXL — Excel exports
- VADER Sentiment — sentiment scoring
- youtube-comment-downloader — retrieving YouTube comments
- yt-dlp — fallback YouTube search

## License

No license is specified in the provided project files. Add a `LICENSE` file if you intend to distribute the project publicly.

## Website – Phase 2: Ad optimizer

The FastAPI website now includes Step 2, an ad optimizer built on the same comment-insight calculations used by the Streamlit application.

### Run the website

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and add your own YouTube and Gemini API keys. Keep `.env` private and do not commit it.
3. Start the website from the project folder:
   ```bash
   python -m uvicorn main:app --reload
   ```
4. Open `http://127.0.0.1:8000`.
5. Complete Step 1 (Sentiment analysis). Once a run finishes, open Step 2 (Ad optimizer) from the navigation or the analysis results page.

### What Step 2 provides

- A per-brand advertising budget saved in the `brands` table.
- Adjustable minimum budget share for each eligible option.
- Source-level recommendations based on purchase claims, buying intent, comment reach and average sentiment.
- Video-level recommendations using the same score, joined with observed video views, likes and channel information.
- Discovery-path, purchase-source, language and location summaries.
- CSV exports for source and video allocations.
- An evidence-coverage warning when fewer than 5% of comments name a source or discovery path.

### How to interpret the recommendations

The optimizer reuses `brand_insights.summarize_group()` and `brand_insights.recommend_budget()` from the original Streamlit project. Its score weights purchase signals most heavily, buying intent next, and weighted reach after that, with a positive-sentiment multiplier. A configurable minimum share is reserved for each eligible option.

These are exploratory recommendations inferred from YouTube comments. They are not verified advertising traffic, sales attribution, conversion rates, or actual campaign performance. Most comments do not name a discovery or purchase source, and the underlying keyword-based detection can miss sarcasm, negation and ambiguous wording.

### Phase status

- Phase 1: website foundation and sentiment analysis.
- Phase 2: ad optimizer (implemented in this update).
- Phase 3: audience clusters and unusual-post detection (implemented in the current website).
- Phase 4: Next.js frontend and table presentation (implemented); authentication and further polish remain optional follow-up work.


## Website – Phase 3: audience clusters and unusual posts

After a sentiment-analysis run finishes, open **Step 3 · Audience clusters** from the results page or the top navigation. Select the number of clusters (2–8) and run the analysis.

### Audience clusters

- Clusters are created from comment-level patterns using sentiment score, purchase claims, buying intent, show-off signals, comment likes/replies/reach weight, language, topic and comment type.
- Each cluster shows its size, positive/negative share, purchase-claim share, buying-intent share, average sentiment and most common topic/language/comment type.
- The app saves cluster profiles in `audience_clusters` and each comment's assignment in `cluster_assignments`. Both tables can be browsed and exported.
- **Interpretation limit:** these are groups of similar comments, not verified groups of unique people. The current data model does not store unique commenter identities.

### Unusual-post detection

- Compares views, likes, comment count, days since posting, engagement rate, average comment sentiment and comment-derived buying intent.
- Uses robust median/MAD outlier scoring with an IQR fallback when the median absolute deviation is zero.
- Posts are flagged only when at least one available metric crosses the outlier threshold; no anomaly is forced when the data does not support one.
- Results are saved in `unusual_posts` and can be exported as CSV.
- An unusual value is not automatically a bad, fraudulent or successful post. It is a statistical signal that deserves human review.

### Additional dependency

Phase 3 uses scikit-learn for K-Means clustering. Install the updated dependencies after extracting the Phase 3 ZIP:

```bash
python -m pip install -r requirements.txt
```

## Next.js frontend (new interface)

The project now includes a separate Next.js App Router frontend in `frontend/`. It replaces the old Jinja pages as the primary user interface while keeping the existing FastAPI, Python analysis modules and SQLite database as the backend. The original server-rendered pages remain available at the FastAPI root if needed.

### Start the Python API

From the `BigDataProject2` project folder, open a terminal and run:

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal running. The backend reads API credentials from the project's server-side `.env` file; credentials are not placed in the browser frontend.

### Start the Next.js website

Open a second terminal:

```bash
cd frontend
npm install
```

Copy `.env.local.example` to `.env.local` (or create `.env.local`) and set:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Then run:

```bash
npm run dev
```

Open `http://localhost:3000`.

### Frontend pages

- `/` — overview and recent analysis runs.
- `/sentiment` — create a sentiment-analysis run and monitor its progress.
- `/optimizer` — configure the budget and view source/video recommendations.
- `/project3` — run audience comment clustering and unusual-post detection.
- `/tables` — browse the eight SQLite tables; table pages include search, run filtering, pagination and CSV export.
- `/runs/{id}` — view an individual analysis run and its results.

### Table presentation

The Next.js data grid uses sticky column headers, consistent row heights, alternating row backgrounds, numeric alignment, compact status pills, truncated multi-line text for long comments/reasons, horizontal scrolling for wide schemas, a search field, pagination and CSV export. On narrow screens, the grid remains scrollable instead of squeezing every column until the table becomes unreadable.

### Running both parts

The Python API and Next.js frontend are two separate processes. Keep both terminals running during local development. The frontend calls the JSON endpoints under `/api/`; the backend permits local development origins on ports `3000` and `8000`.
