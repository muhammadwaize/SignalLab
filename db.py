"""
SQLite storage for the website (Python standard library only, no extra install).

Tables:
  brands          one row per brand (its own budget)
  analysis_runs   one row per sentiment-analysis run (settings, progress, status)
  videos          Table A of Project 3: the posts (post_id, platform, content_type, likes, views ...)
  comments        Table B of Project 3: the comments (comment_text, language_type, topic, sentiment, purchase_intent ...)
  topic_results   summary of the topics people talk about, per run
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd

from content_types import classify, days_since
from topics import topic_summary

DB_PATH = os.environ.get("APP_DB", "website.db")
TABLES = ["brands", "analysis_runs", "videos", "comments", "topic_results", "audience_clusters", "cluster_assignments", "unusual_posts"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    niche TEXT DEFAULT '',
    budget_rs REAL DEFAULT 1000000,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER REFERENCES brands(id),
    brand TEXT, niche TEXT DEFAULT '',
    max_videos INTEGER, per_video INTEGER, total_comments INTEGER,
    strict INTEGER DEFAULT 1, recent INTEGER DEFAULT 0, extra_links TEXT DEFAULT '',
    exclude_words TEXT DEFAULT '', region TEXT DEFAULT '',
    status TEXT DEFAULT 'queued', progress REAL DEFAULT 0, message TEXT DEFAULT '',
    notes TEXT DEFAULT '[]', error TEXT DEFAULT '',
    n_videos INTEGER DEFAULT 0, n_comments INTEGER DEFAULT 0,
    created_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES analysis_runs(id),
    post_id TEXT, brand TEXT, platform TEXT, campaign TEXT, content_type TEXT, product_category TEXT,
    title TEXT, channel TEXT,
    likes INTEGER, comments_count INTEGER, shares INTEGER, views INTEGER, days_since_post INTEGER,
    comments_scraped INTEGER,
    source_url TEXT, collected_at TEXT, data_origin TEXT
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES analysis_runs(id),
    post_id TEXT, brand TEXT, platform TEXT,
    comment_text TEXT, likes INTEGER, replies INTEGER, weight REAL,
    language_type TEXT, topic TEXT, sentiment TEXT, compound REAL, purchase_intent TEXT, comment_type TEXT,
    source TEXT, discovered_on TEXT, bought_from TEXT,
    word_of_mouth INTEGER, saw_ad INTEGER, influencer INTEGER, location TEXT,
    purchased INTEGER, intent INTEGER, show_off INTEGER,
    collected_at TEXT, data_origin TEXT
);
CREATE TABLE IF NOT EXISTS topic_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES analysis_runs(id),
    topic TEXT, comments INTEGER, positive_pct REAL, negative_pct REAL, avg_sentiment REAL, verdict TEXT
);
CREATE INDEX IF NOT EXISTS idx_comments_run ON comments(run_id);
CREATE INDEX IF NOT EXISTS idx_videos_run ON videos(run_id);
CREATE INDEX IF NOT EXISTS idx_topics_run ON topic_results(run_id);
CREATE TABLE IF NOT EXISTS audience_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    cluster_no INTEGER NOT NULL,
    label TEXT, description TEXT,
    comment_count INTEGER DEFAULT 0,
    positive_pct REAL, negative_pct REAL, purchase_pct REAL, intent_pct REAL,
    avg_sentiment REAL, top_topic TEXT, top_language TEXT, top_comment_type TEXT,
    created_at TEXT,
    UNIQUE(run_id, cluster_no)
);
CREATE TABLE IF NOT EXISTS cluster_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    comment_id INTEGER NOT NULL,
    cluster_no INTEGER NOT NULL,
    UNIQUE(run_id, comment_id)
);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_run ON cluster_assignments(run_id);
CREATE TABLE IF NOT EXISTS unusual_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    video_id TEXT, title TEXT, channel TEXT,
    views INTEGER, likes INTEGER, comments_count INTEGER,
    engagement_rate_pct REAL, avg_comment_sentiment REAL, purchase_intent_pct REAL,
    anomaly_count INTEGER, reasons TEXT, source_url TEXT, data_origin TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_unusual_posts_run ON unusual_posts(run_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


NEW_COLUMNS = {"analysis_runs": {"exclude_words": "TEXT DEFAULT ''", "region": "TEXT DEFAULT ''"}}


def _migrate(conn) -> None:
    """Add columns that older copies of website.db do not have yet (keeps your saved data)."""
    for table, columns in NEW_COLUMNS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for column, ddl in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")     # lets the page read while a job is writing
        conn.executescript(SCHEMA)
        _migrate(conn)
        # a run that was still going when the server stopped can never finish
        conn.execute("UPDATE analysis_runs SET status='failed', error='The server was restarted during this run.', "
                     "finished_at=? WHERE status IN ('queued','running')", (now(),))


# ---------- runs ----------
def create_run(brand: str, niche: str, max_videos: int, per_video: int, total_comments: int,
               strict: bool, recent: bool, extra_links: str, exclude_words: str = "", region: str = "") -> int:
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO brands (name, niche, created_at) VALUES (?,?,?)", (brand, niche, now()))
        conn.execute("UPDATE brands SET niche=? WHERE name=? AND ?<>''", (niche, brand, niche))
        brand_id = conn.execute("SELECT id FROM brands WHERE name=?", (brand,)).fetchone()["id"]
        cur = conn.execute(
            "INSERT INTO analysis_runs (brand_id, brand, niche, max_videos, per_video, total_comments, strict, recent, "
            "extra_links, exclude_words, region, status, message, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,'queued','Waiting to start...',?)",
            (brand_id, brand, niche, max_videos, per_video, total_comments, int(strict), int(recent), extra_links,
             exclude_words, region, now()))
        return cur.lastrowid


def update_run(run_id: int, **fields) -> None:
    cols = ", ".join(f"{k}=?" for k in fields)
    with connect() as conn:
        conn.execute(f"UPDATE analysis_runs SET {cols} WHERE id=?", (*fields.values(), run_id))


def delete_run(run_id: int) -> None:
    """Remove a run and every row saved for it (the brand itself stays)."""
    with connect() as conn:
        for table in ("audience_clusters", "cluster_assignments", "unusual_posts", "topic_results", "comments", "videos"):
            conn.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM analysis_runs WHERE id=?", (run_id,))


def get_run(run_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None


def list_runs() -> list:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM analysis_runs ORDER BY id DESC").fetchall()]


# ---------- saving the results of a run ----------
def save_results(run_id: int, brand: str, niche: str, comments: pd.DataFrame, videos: pd.DataFrame) -> None:
    stamp = now()
    video_rows = []
    for v in videos.to_dict("records"):
        content_type, campaign = classify(v["title"], brand)
        video_rows.append((
            run_id, v["video_id"], brand, "YouTube", campaign, content_type, niche, v["title"], v["channel"],
            int(v.get("likes") or 0), int(v.get("comment_count") or 0), None, int(v.get("views") or 0),
            days_since(v.get("published")), int(v.get("comments_scraped") or 0),
            f"https://www.youtube.com/watch?v={v['video_id']}", stamp, "observed"))

    comment_rows = []
    for r in comments.itertuples(index=False):
        intent_label = "Bought it" if r.purchased else ("Wants to buy" if r.intent else "No signal")
        comment_rows.append((
            run_id, r.video_id, brand, "YouTube", r.comment, int(r.likes), int(r.replies), float(r.weight),
            r.language, r.topics, r.sentiment, float(r.compound), intent_label, r.comment_type,
            r.source, r.discovered_on, r.bought_from, int(r.word_of_mouth), int(r.saw_ad), int(r.influencer),
            r.location, int(r.purchased), int(r.intent), int(r.show_off), stamp, "observed"))

    topics = topic_summary(comments)
    topic_rows = [(run_id, t["topic"], int(t["comments"]), float(t["positive_%"]), float(t["negative_%"]),
                   float(t["avg_sentiment"]), t["verdict"]) for t in topics.to_dict("records")]

    with connect() as conn:
        conn.executemany("INSERT INTO videos (run_id, post_id, brand, platform, campaign, content_type, product_category, "
                         "title, channel, likes, comments_count, shares, views, days_since_post, comments_scraped, "
                         "source_url, collected_at, data_origin) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", video_rows)
        conn.executemany("INSERT INTO comments (run_id, post_id, brand, platform, comment_text, likes, replies, weight, "
                         "language_type, topic, sentiment, compound, purchase_intent, comment_type, source, discovered_on, "
                         "bought_from, word_of_mouth, saw_ad, influencer, location, purchased, intent, show_off, "
                         "collected_at, data_origin) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", comment_rows)
        conn.executemany("INSERT INTO topic_results (run_id, topic, comments, positive_pct, negative_pct, avg_sentiment, "
                         "verdict) VALUES (?,?,?,?,?,?,?)", topic_rows)


# ---------- reading a run back (same column names the analysis code already uses) ----------
BOOL_COLS = ["word_of_mouth", "saw_ad", "influencer", "purchased", "intent", "show_off"]


def load_comments(run_id: int) -> pd.DataFrame:
    sql = """SELECT c.id, c.run_id, c.post_id AS video_id, c.brand, c.comment_text AS comment, c.likes, c.replies,
                    c.weight, c.language_type AS language, c.topic AS topics, c.sentiment, c.compound,
                    c.purchase_intent, c.comment_type, c.source, c.discovered_on, c.bought_from, c.word_of_mouth,
                    c.saw_ad, c.influencer, c.location, c.purchased, c.intent, c.show_off, v.title AS video_title
             FROM comments c LEFT JOIN videos v ON v.run_id = c.run_id AND v.post_id = c.post_id
             WHERE c.run_id = ?"""
    with connect() as conn:
        df = pd.read_sql_query(sql, conn, params=(run_id,))
    for col in BOOL_COLS:
        df[col] = df[col].astype(bool)
    df["topics"] = df["topics"].fillna("")
    return df


def load_videos(run_id: int) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query("SELECT * FROM videos WHERE run_id = ? ORDER BY views DESC", conn, params=(run_id,))


# ---------- browsing tables ----------
def table_columns(name: str) -> list:
    with connect() as conn:
        return [r["name"] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()]


def table_count(name: str, run_id: int | None = None) -> int:
    with connect() as conn:
        if run_id and "run_id" in table_columns(name):
            return conn.execute(f"SELECT COUNT(*) AS n FROM {name} WHERE run_id=?", (run_id,)).fetchone()["n"]
        return conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"]


def table_rows(name: str, run_id: int | None = None, limit: int = 100, offset: int = 0) -> list:
    where, params = "", []
    if run_id and "run_id" in table_columns(name):
        where, params = "WHERE run_id=?", [run_id]
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM {name} {where} ORDER BY id LIMIT ? OFFSET ?", (*params, limit, offset))
        return [dict(r) for r in rows.fetchall()]


def iter_table_rows(name: str, run_id: int | None = None, chunk: int = 2000):
    """Yield every row (in chunks) for the CSV download."""
    offset = 0
    while True:
        rows = table_rows(name, run_id, chunk, offset)
        if not rows:
            return
        yield from rows
        offset += chunk


# ---------- brand budget settings (Step 2: Ad optimizer) ----------
def get_brand_by_name(name: str):
    with connect() as conn:
        row = conn.execute("SELECT * FROM brands WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None


def update_brand_budget(name: str, budget_rs: float) -> None:
    with connect() as conn:
        conn.execute("UPDATE brands SET budget_rs=? WHERE name=?", (float(budget_rs), name))


# ---------- Project 3: audience clusters and unusual posts ----------
def save_cluster_results(run_id: int, profiles: list, assignments: list) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM cluster_assignments WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM audience_clusters WHERE run_id=?", (run_id,))
        conn.executemany(
            "INSERT INTO audience_clusters (run_id, cluster_no, label, description, comment_count, positive_pct, "
            "negative_pct, purchase_pct, intent_pct, avg_sentiment, top_topic, top_language, top_comment_type, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, p["cluster_no"], p["label"], p["description"], p["comment_count"], p["positive_pct"],
              p["negative_pct"], p["purchase_pct"], p["intent_pct"], p["avg_sentiment"], p["top_topic"],
              p["top_language"], p["top_comment_type"], p["created_at"]) for p in profiles])
        conn.executemany(
            "INSERT INTO cluster_assignments (run_id, comment_id, cluster_no) VALUES (?,?,?)",
            [(run_id, comment_id, cluster_no) for comment_id, cluster_no in assignments])


def load_cluster_profiles(run_id: int) -> list:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM audience_clusters WHERE run_id=? ORDER BY cluster_no", (run_id,)).fetchall()]


def load_cluster_assignments(run_id: int) -> list:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT a.comment_id, a.cluster_no, c.comment_text, c.sentiment, c.compound, c.topic, "
            "c.language_type, c.purchase_intent, c.likes, c.post_id "
            "FROM cluster_assignments a JOIN comments c ON c.id=a.comment_id "
            "WHERE a.run_id=? ORDER BY a.cluster_no, a.comment_id", (run_id,)).fetchall()]


def save_unusual_posts(run_id: int, posts: list) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM unusual_posts WHERE run_id=?", (run_id,))
        conn.executemany(
            "INSERT INTO unusual_posts (run_id, video_id, title, channel, views, likes, comments_count, "
            "engagement_rate_pct, avg_comment_sentiment, purchase_intent_pct, anomaly_count, reasons, source_url, "
            "data_origin, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, p["video_id"], p["title"], p["channel"], p["views"], p["likes"], p["comments_count"],
              p["engagement_rate_pct"], p["avg_comment_sentiment"], p["purchase_intent_pct"], p["anomaly_count"],
              p["reasons"], p["source_url"], p["data_origin"], now()) for p in posts])


def load_unusual_posts(run_id: int) -> list:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM unusual_posts WHERE run_id=? ORDER BY anomaly_count DESC, views DESC", (run_id,)).fetchall()]
