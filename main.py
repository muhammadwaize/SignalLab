"""
Brand Intelligence website (FastAPI + SQLite)

Run (from this folder):
    python -m uvicorn main:app
then open  http://127.0.0.1:8000

Step 1  Sentiment analysis   -> saved in the tables  brands, analysis_runs, videos, comments, topic_results
Step 2  Ad optimizer         -> comment-derived budget recommendations
Step 3  Audience clusters    -> comment clustering and unusual-post detection
Keys (YOUTUBE_API_KEY, GEMINI_API_KEY, ...) are read from the .env file on the server and never reach the browser.
"""

import csv
import io
import json
import math
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request, Body
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import db
import jobs
import project3
import pandas as pd
from brand_insights import (coverage, discovery_summary, language_summary, recommend_budget, summarize_group)
from topics import topic_summary, type_summary

BASE = Path(__file__).parent
PAGE_SIZE = 100


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Brand Intelligence", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


def num(value):
    """Friendly numbers for the tables: 1,250  and  0.215"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else ""
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{int(value):,}" if value == int(value) else f"{value:,.3f}".rstrip("0").rstrip(".")
    return value


templates.env.filters["num"] = num


def page(request: Request, name: str, context: dict, status_code: int = 200):
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def parse_run_id(value: Optional[str]) -> Optional[int]:
    return int(value) if value and value.strip().isdigit() else None


# ---------- Home ----------
@app.get("/")
def home(request: Request):
    return page(request, "index.html", {"active": "home", "runs": db.list_runs()})


# ---------- Step 1: sentiment analysis ----------
FORM_DEFAULTS = {"brand": "", "niche": "", "max_videos": 10, "per_video": 300, "total_comments": 2000,
                 "strict": True, "order": "popular", "extra_links": "", "exclude_words": "", "region": ""}


@app.get("/analysis/new")
def new_analysis(request: Request):
    return page(request, "new_analysis.html", {"active": "sentiment", "form": FORM_DEFAULTS, "error": ""})


@app.post("/analysis")
def create_analysis(request: Request, brand: str = Form(""), niche: str = Form(""), max_videos: int = Form(10),
                    per_video: int = Form(300), total_comments: int = Form(2000), strict: Optional[str] = Form(None),
                    order: str = Form("popular"), extra_links: str = Form(""), exclude_words: str = Form(""),
                    region: str = Form("")):
    form = {"brand": brand.strip(), "niche": niche.strip(), "max_videos": max(1, min(max_videos, 50)),
            "per_video": max(20, min(per_video, 3000)), "total_comments": max(50, min(total_comments, 50000)),
            "strict": strict is not None, "order": order, "extra_links": extra_links,
            "exclude_words": exclude_words.strip(), "region": region.strip()}
    if not form["brand"]:
        return page(request, "new_analysis.html",
                    {"active": "sentiment", "form": form, "error": "Please enter a brand name."}, 400)
    run_id = db.create_run(form["brand"], form["niche"], form["max_videos"], form["per_video"],
                           form["total_comments"], form["strict"], order == "recent", extra_links,
                           form["exclude_words"], form["region"])
    jobs.start(run_id)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/delete")
def delete_run(run_id: int):
    db.delete_run(run_id)
    return RedirectResponse("/", status_code=303)


@app.get("/api/runs/{run_id}/status")
def run_status(run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return JSONResponse({k: run[k] for k in ("status", "progress", "message", "error")})


def results_context(run: dict) -> dict:
    df, videos = db.load_comments(run["id"]), db.load_videos(run["id"])
    total = len(df)
    pct = lambda mask: round(float(mask.mean()) * 100) if total else 0
    types = type_summary(df).to_dict("records")
    top = max([t["comments"] for t in types] + [1])
    for t in types:
        t["bar"] = round(t["comments"] / top * 100)

    def best(mask):
        return df[mask].sort_values("likes", ascending=False).head(5).to_dict("records")

    return {
        "metrics": {"comments": total, "videos": int(df["video_id"].nunique()),
                    "positive": pct(df["compound"] >= 0.05), "negative": pct(df["compound"] <= -0.05),
                    "bought": int(df["purchased"].sum()), "want": int(df["intent"].sum())},
        "types": types, "topics": topic_summary(df).to_dict("records"),
        "top_positive": best(df["compound"] >= 0.05), "top_negative": best(df["compound"] <= -0.05),
        "videos": videos.to_dict("records"), "notes": json.loads(run["notes"] or "[]"),
    }


@app.get("/runs/{run_id}")
def run_page(request: Request, run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    context = {"active": "sentiment", "run": run}
    if run["status"] == "done":
        context.update(results_context(run))
    return page(request, "run.html", context)




# ---------- Step 2: ad optimizer ----------
def optimizer_context(run: dict, budget: float, min_share: float) -> dict:
    """Build the same evidence-led budget recommendations used by the Streamlit optimizer."""
    comments = db.load_comments(run["id"])
    videos = db.load_videos(run["id"])

    source = summarize_group(comments, "source") if not comments.empty else pd.DataFrame()
    discovered = summarize_group(comments, "discovered_on") if not comments.empty else pd.DataFrame()
    bought = summarize_group(comments, "bought_from") if not comments.empty else pd.DataFrame()
    locations = summarize_group(comments, "location") if not comments.empty else pd.DataFrame()
    languages = language_summary(comments) if not comments.empty else pd.DataFrame()
    found = discovery_summary(comments) if not comments.empty else pd.DataFrame()
    cov = coverage(comments) if not comments.empty else {
        "comments": 0, "named_any": 0, "named_any_%": 0.0, "found_on_platform": 0,
        "bought_from_named": 0, "say_bought": 0, "friend_ad_influencer": 0
    }

    video_summary = summarize_group(comments, "video_id", skip=()) if not comments.empty else pd.DataFrame()
    if not video_summary.empty and not videos.empty:
        video_info = videos.rename(columns={"post_id": "video_id"})
        keep = [c for c in ("video_id", "title", "channel", "views", "likes", "comments_count") if c in video_info]
        video_summary = video_summary.merge(video_info[keep].drop_duplicates("video_id"), on="video_id", how="left")

    source_alloc = recommend_budget(source, budget, min_share) if not source.empty else source
    video_alloc = recommend_budget(video_summary, budget, min_share) if not video_summary.empty else video_summary

    def records(frame):
        if frame is None or frame.empty:
            return []
        return frame.replace({float("nan"): None}).to_dict("records")

    return {"run": run, "budget": int(budget), "min_share": min_share, "coverage": cov,
            "source": records(source), "discovered": records(discovered), "bought": records(bought),
            "discovery": records(found), "languages": records(languages), "locations": records(locations),
            "source_alloc": records(source_alloc), "video_alloc": records(video_alloc),
            "has_comments": not comments.empty}


@app.get("/optimizer")
def optimizer_home(request: Request):
    runs = [r for r in db.list_runs() if r["status"] == "done"]
    if runs:
        return RedirectResponse(f"/optimizer/{runs[0]['id']}", status_code=303)
    return page(request, "optimizer_empty.html", {"active": "optimizer", "runs": db.list_runs()})


@app.get("/optimizer/{run_id}")
def optimizer_page(request: Request, run_id: int, min_share: float = 0.05):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "The sentiment analysis must finish before the ad optimizer can run.")
    brand = db.get_brand_by_name(run["brand"]) or {}
    budget = float(brand.get("budget_rs") or 1_000_000)
    min_share = max(0.0, min(float(min_share), 0.15))
    context = optimizer_context(run, budget, min_share)
    context.update({"active": "optimizer", "runs": [r for r in db.list_runs() if r["status"] == "done"],
                    "min_share_pct": round(min_share * 100, 1)})
    return page(request, "optimizer.html", context)


@app.post("/optimizer/{run_id}")
def save_optimizer_settings(request: Request, run_id: int, budget_rs: float = Form(...),
                            min_share_pct: float = Form(5)):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "The sentiment analysis must finish before the ad optimizer can run.")
    budget = max(10_000.0, min(float(budget_rs), 1_000_000_000.0))
    min_share = max(0.0, min(float(min_share_pct), 15.0))
    db.update_brand_budget(run["brand"], budget)
    return RedirectResponse(f"/optimizer/{run_id}?min_share={min_share / 100}", status_code=303)


@app.get("/optimizer/{run_id}/csv")
def optimizer_csv(run_id: int, kind: str = "sources"):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "The sentiment analysis must finish before the ad optimizer can run.")
    brand = db.get_brand_by_name(run["brand"]) or {}
    data = optimizer_context(run, float(brand.get("budget_rs") or 1_000_000), 0.05)
    rows = data["video_alloc"] if kind == "videos" else data["source_alloc"]
    columns = list(rows[0].keys()) if rows else []
    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        buf.write("\ufeff")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])
        yield buf.getvalue()
    filename = f"{run['brand'].replace(' ', '_')}_optimizer_{kind}.csv"
    return StreamingResponse(generate(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ---------- Step 3: Project 3 audience clusters and unusual posts ----------
def project3_context(run: dict, message: str = "", error: str = "") -> dict:
    profiles = db.load_cluster_profiles(run["id"])
    assignments = db.load_cluster_assignments(run["id"])
    unusual = db.load_unusual_posts(run["id"])
    comments = db.load_comments(run["id"])
    videos = db.load_videos(run["id"])
    return {
        "active": "clusters", "run": run,
        "runs": [r for r in db.list_runs() if r["status"] == "done"],
        "profiles": profiles, "assignments": assignments, "unusual": unusual,
        "comment_count": len(comments), "video_count": len(videos),
        "clustered_count": len(assignments), "message": message, "error": error,
        "has_results": bool(profiles or unusual),
    }


@app.get("/project3")
def project3_home(request: Request):
    runs = [r for r in db.list_runs() if r["status"] == "done"]
    if runs:
        return RedirectResponse(f"/project3/{runs[0]['id']}", status_code=303)
    return page(request, "project3_empty.html", {"active": "clusters", "runs": db.list_runs()})


@app.get("/project3/{run_id}")
def project3_page(request: Request, run_id: int, message: str = "", error: str = ""):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "Sentiment analysis must finish before Project 3 can run.")
    return page(request, "project3.html", project3_context(run, message, error))


@app.post("/project3/{run_id}/run")
def run_project3_analysis(run_id: int, n_clusters: int = Form(4)):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "Sentiment analysis must finish before Project 3 can run.")
    errors = []
    completed = []
    try:
        result = project3.cluster_comments(run_id, n_clusters=max(2, min(int(n_clusters), 8)))
        completed.append(f"Created {result['n_clusters']} audience clusters from {result['assignments_count']} comments")
    except ValueError as exc:
        errors.append(str(exc))
    try:
        result = project3.detect_unusual_posts(run_id)
        completed.append(f"Checked {result['posts_checked']} posts; flagged {result['flagged_count']} unusual posts")
    except ValueError as exc:
        errors.append(str(exc))
    message = ". ".join(completed)
    error = ". ".join(errors)
    return RedirectResponse(f"/project3/{run_id}?{urlencode({'message': message, 'error': error})}", status_code=303)


@app.get("/project3/{run_id}/csv")
def project3_csv(run_id: int, kind: str = "clusters"):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if kind == "assignments":
        rows = db.load_cluster_assignments(run_id)
    elif kind == "posts":
        rows = db.load_unusual_posts(run_id)
    else:
        rows = db.load_cluster_profiles(run_id)
    columns = list(rows[0].keys()) if rows else []
    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        buf.write("\ufeff")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])
        yield buf.getvalue()
    filename = f"{run['brand'].replace(' ', '_')}_project3_{kind}.csv"
    return StreamingResponse(generate(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ---------- Data tables ----------
@app.get("/tables")
def tables_home(request: Request):
    info = [{"name": t, "rows": db.table_count(t), "columns": db.table_columns(t)} for t in db.TABLES]
    return page(request, "tables.html", {"active": "tables", "tables": info})


def check_table(name: str) -> str:
    if name not in db.TABLES:
        raise HTTPException(404, "No such table")
    return name


@app.get("/tables/{name}")
def table_view(request: Request, name: str, page_no: int = 1, run_id: Optional[str] = None):
    check_table(name)
    rid = parse_run_id(run_id)
    columns = db.table_columns(name)
    total = db.table_count(name, rid)
    pages = max(1, -(-total // PAGE_SIZE))
    page_no = max(1, min(page_no, pages))
    rows = db.table_rows(name, rid, PAGE_SIZE, (page_no - 1) * PAGE_SIZE)
    return page(request, "table_view.html", {
        "active": "tables", "name": name, "columns": columns, "rows": rows, "total": total, "page_no": page_no,
        "pages": pages, "run_id": rid or "", "has_run": "run_id" in columns, "runs": db.list_runs()})


@app.get("/tables/{name}/csv")
def table_csv(name: str, run_id: Optional[str] = None):
    check_table(name)
    rid = parse_run_id(run_id)
    columns = db.table_columns(name)

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        buf.write("\ufeff")                      # lets Excel read Urdu text correctly
        writer.writerow(columns)
        for row in db.iter_table_rows(name, rid):
            writer.writerow([row[c] for c in columns])
            if buf.tell() > 65536:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)
        yield buf.getvalue()

    suffix = f"_run{rid}" if rid else ""
    return StreamingResponse(generate(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}{suffix}.csv"'})


def _json_safe(value):
    """Convert pandas/numpy scalars and missing values to strict JSON values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


# ---------- JSON API for the Next.js frontend ----------
@app.get("/api/dashboard")
def api_dashboard():
    runs = db.list_runs()
    done = [r for r in runs if r["status"] == "done"]
    total_comments = sum(int(r.get("n_comments") or 0) for r in done)
    total_videos = sum(int(r.get("n_videos") or 0) for r in done)
    return _json_safe({"runs": runs[:8], "metrics": {"runs": len(runs), "completed": len(done),
            "comments": total_comments, "videos": total_videos}})


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "SignalLab API"}

@app.get("/api/runs")
def api_runs():
    return _json_safe({"runs": db.list_runs()})


@app.post("/api/runs")
def api_create_run(payload: dict = Body(...)):
    brand = str(payload.get("brand", "")).strip()
    if not brand:
        raise HTTPException(400, "Please enter a brand name.")
    niche = str(payload.get("niche", "")).strip()
    max_videos = max(1, min(int(payload.get("max_videos", 10)), 50))
    per_video = max(20, min(int(payload.get("per_video", 300)), 3000))
    total_comments = max(50, min(int(payload.get("total_comments", 2000)), 50000))
    strict = bool(payload.get("strict", True))
    order = str(payload.get("order", "popular"))
    extra_links = str(payload.get("extra_links", ""))
    exclude_words = str(payload.get("exclude_words", "")).strip()
    region = str(payload.get("region", "")).strip()
    run_id = db.create_run(brand, niche, max_videos, per_video, total_comments, strict,
                           order == "recent", extra_links, exclude_words, region)
    jobs.start(run_id)
    return {"run_id": run_id, "status": "queued"}


@app.get("/api/runs/{run_id}")
def api_run_detail(run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    result = {"run": run}
    if run["status"] == "done":
        result["results"] = results_context(run)
    return _json_safe(result)


@app.get("/api/tables")
def api_tables():
    return _json_safe({"tables": [{"name": t, "rows": db.table_count(t), "columns": db.table_columns(t)} for t in db.TABLES]})


@app.get("/api/tables/{name}")
def api_table_rows(name: str, page_no: int = 1, run_id: Optional[str] = None, q: str = ""):
    check_table(name)
    rid = parse_run_id(run_id)
    columns = db.table_columns(name)
    clauses, params = [], []
    if rid and "run_id" in columns:
        clauses.append("run_id = ?")
        params.append(rid)
    if q.strip():
        clauses.append("(" + " OR ".join(f'CAST("{col}" AS TEXT) LIKE ?' for col in columns) + ")")
        params.extend([f"%{q.strip()}%"] * len(columns))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    page_size = 50
    with db.connect() as conn:
        total = conn.execute(f'SELECT COUNT(*) AS n FROM "{name}"{where}', params).fetchone()["n"]
        pages = max(1, -(-total // page_size))
        page_no = max(1, min(page_no, pages))
        rows = [dict(r) for r in conn.execute(
            f'SELECT * FROM "{name}"{where} ORDER BY id LIMIT ? OFFSET ?',
            (*params, page_size, (page_no - 1) * page_size)).fetchall()]
    return _json_safe({"name": name, "columns": columns, "rows": rows, "total": total,
            "page": page_no, "page_size": page_size, "pages": pages,
            "runs": db.list_runs(), "has_run": "run_id" in columns})


@app.get("/api/optimizer/{run_id}")
def api_optimizer(run_id: int, min_share: float = 0.05):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "The sentiment analysis must finish before the ad optimizer can run.")
    brand = db.get_brand_by_name(run["brand"]) or {}
    budget = float(brand.get("budget_rs") or 1_000_000)
    min_share = max(0.0, min(float(min_share), 0.15))
    return _json_safe(optimizer_context(run, budget, min_share))


@app.post("/api/optimizer/{run_id}")
def api_save_optimizer(run_id: int, payload: dict = Body(...)):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "The sentiment analysis must finish before the ad optimizer can run.")
    budget = max(10_000.0, min(float(payload.get("budget_rs", 1_000_000)), 1_000_000_000.0))
    db.update_brand_budget(run["brand"], budget)
    return _json_safe({"ok": True, "budget_rs": budget})


@app.get("/api/project3/{run_id}")
def api_project3(run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "Sentiment analysis must finish before Project 3 can run.")
    return _json_safe(project3_context(run))


@app.post("/api/project3/{run_id}/run")
def api_run_project3(run_id: int, payload: dict = Body(default={} )):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Analysis run not found")
    if run["status"] != "done":
        raise HTTPException(409, "Sentiment analysis must finish before Project 3 can run.")
    n_clusters = max(2, min(int(payload.get("n_clusters", 4)), 8))
    completed, errors = [], []
    try:
        result = project3.cluster_comments(run_id, n_clusters=n_clusters)
        completed.append(f"Created {result['n_clusters']} clusters from {result['assignments_count']} comments")
    except ValueError as exc:
        errors.append(str(exc))
    try:
        result = project3.detect_unusual_posts(run_id)
        completed.append(f"Checked {result['posts_checked']} posts; flagged {result['flagged_count']} unusual posts")
    except ValueError as exc:
        errors.append(str(exc))
    return _json_safe({"message": ". ".join(completed), "error": ". ".join(errors), **project3_context(run)})
