"""
Background jobs: collecting comments takes a minute or more, so it runs in its own thread while the page
shows a progress bar. Progress and the final status are written to the analysis_runs table.
"""

import json
import threading

import db
from brand_pipeline import collect_brand_data
from config import get_key, scrub


def start(run_id: int) -> None:
    threading.Thread(target=_run, args=(run_id,), daemon=True).start()


def _run(run_id: int) -> None:
    yt_key = get_key("YOUTUBE_API_KEY")
    try:
        run = db.get_run(run_id)
        db.update_run(run_id, status="running", progress=0.01, message="Starting...")

        def progress(fraction, text):
            db.update_run(run_id, progress=round(float(fraction), 3), message=str(text)[:200])

        comments, videos, notes = collect_brand_data(
            run["brand"], run["niche"], run["max_videos"], run["per_video"], run["total_comments"], yt_key,
            bool(run["strict"]), bool(run["recent"]), run["extra_links"].split(), progress=progress,
            exclude=[w for w in (run["exclude_words"] or "").split(",") if w.strip()], region=run["region"] or "")
        if comments.empty:
            raise RuntimeError("No comments could be read. " + " ".join(notes))

        db.update_run(run_id, message="Saving the results to the tables...")
        db.save_results(run_id, run["brand"], run["niche"], comments, videos)
        db.update_run(run_id, status="done", progress=1.0, message="Done", notes=json.dumps(notes),
                      n_videos=int(comments["video_id"].nunique()), n_comments=int(len(comments)),
                      finished_at=db.now())
    except Exception as e:
        db.update_run(run_id, status="failed", error=scrub(e, yt_key)[:500], message="Failed", finished_at=db.now())
