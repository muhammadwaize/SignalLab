
"""
Brand pipeline: brand name -> videos -> comments -> sentiment + buying signals + topics.
Progress is reported continuously during comment scraping.
"""

import os
import re
import threading
from itertools import islice
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from youtube_comment_downloader import (
    SORT_BY_POPULAR,
    SORT_BY_RECENT,
    YoutubeCommentDownloader
)

from topics import add_comment_types
from youtube_search import search_videos
from youtube_sentiment import analyze, extract_video_id


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "brand"


def fetch_video_comments(
    video_id: str,
    limit: int,
    recent: bool = False,
    on_progress=None
) -> list[dict]:
    downloader = YoutubeCommentDownloader()
    sort = SORT_BY_RECENT if recent else SORT_BY_POPULAR
    comments = downloader.get_comments(video_id, sort_by=sort)

    collected = []

    for comment in islice(comments, limit):
        collected.append({
            "text": comment["text"],
            "votes": comment.get("votes", "0"),
            "replies": comment.get("replies", 0)
        })

        if on_progress and (
            len(collected) % 10 == 0 or len(collected) == limit
        ):
            on_progress(len(collected))

    return collected


def collect_brand_data(
    brand: str,
    niche: str = "",
    max_videos: int = 10,
    per_video: int = 300,
    total_comments: int = 2000,
    api_key: str = "",
    strict: bool = True,
    recent: bool = False,
    extra_links: list[str] | None = None,
    progress=None,
    exclude: list[str] | None = None,
    region: str = ""
):
    """Returns (comments_df, videos_df, notes)."""

    say = progress or (lambda fraction, text: None)
    notes = []

    say(0.02, f"Searching YouTube for {brand}...")

    videos, mode, search_notes = search_videos(
        brand, niche, max_videos, api_key, strict, exclude, region
    )

    notes += search_notes
    notes.append(f"Found {len(videos)} video(s) using {mode}.")

    # Add manually supplied video links.
    known = {v["video_id"] for v in videos}

    for link in extra_links or []:
        vid = extract_video_id(link)

        if vid and vid not in known:
            videos.append({
                "video_id": vid,
                "title": f"(added by you) {vid}",
                "channel": "",
                "published": "",
                "views": 0,
                "likes": 0,
                "comment_count": 0
            })
            known.add(vid)

        elif not vid:
            notes.append(f"Skipped invalid link: {link}")

    if not videos:
        raise RuntimeError(
            "No videos found. Try turning off 'only videos that mention "
            "the brand', check the spelling, or add video links by hand."
        )

    fetch_limit = max(0, min(per_video, total_comments))
    results = {}

    # Shared progress information for concurrent scraping workers.
    lock = threading.Lock()
    video_progress = {
        i: 0.0 for i in range(len(videos))
    }

    def update_scraping_progress(index, count):
        with lock:
            video_progress[index] = min(
                1.0, count / max(fetch_limit, 1)
            )

            overall = sum(video_progress.values()) / len(videos)
            fraction = 0.05 + (0.45 * overall)

            say(
                fraction,
                f"Scraping comments: {sum(video_progress.values()):.1f}/"
                f"{len(videos)} video-equivalents completed..."
            )

    def scrape_one(index, video):
        def report(count):
            update_scraping_progress(index, count)

        comments = fetch_video_comments(
            video["video_id"],
            fetch_limit,
            recent,
            on_progress=report
        )

        update_scraping_progress(index, fetch_limit)

        return comments

    # Download comments concurrently.
    if fetch_limit > 0:
        say(0.05, f"Starting comment collection from {len(videos)} videos...")

        with ThreadPoolExecutor(
            max_workers=min(3, len(videos)),
            thread_name_prefix="youtube-scraper"
        ) as executor:

            futures = {
                executor.submit(scrape_one, i, video): i
                for i, video in enumerate(videos)
            }

            for future in as_completed(futures):
                index = futures[future]

                try:
                    results[index] = (future.result(), None)

                except Exception as e:
                    results[index] = (None, str(e))

                    with lock:
                        video_progress[index] = 1.0
                        overall = sum(video_progress.values()) / len(videos)
                        say(
                            0.05 + 0.45 * overall,
                            f"Finished collecting available comments "
                            f"from {sum(1 for v in video_progress.values() if v >= 1)}"
                            f"/{len(videos)} videos..."
                        )

    # Process downloaded comments in their original video order.
    frames = []
    kept = []
    used = 0

    for i, video in enumerate(videos):
        remaining = total_comments - used

        if remaining <= 0:
            notes.append("Reached the total comment limit.")
            break

        say(
            0.52 + 0.35 * (i / len(videos)),
            f"Analyzing comments from video {i + 1}/{len(videos)}: "
            f"{video['title'][:45]}"
        )

        comments, error = results.get(i, (None, None))

        if error:
            notes.append(
                f"Could not read {video['video_id']}: {error}"
            )
            continue

        if not comments:
            notes.append(
                f"No comments on '{video['title'][:50]}' "
                "(comments may be off)."
            )
            continue

        comments = comments[:remaining]

        df = analyze(comments, video["video_id"])

        if df.empty:
            continue

        df["video_title"] = video["title"]
        df["channel"] = video["channel"]
        df["video_views"] = video.get("views", 0)

        frames.append(df)
        used += len(df)

        kept.append({
            **{
                key: video.get(key, "")
                for key in (
                    "video_id",
                    "title",
                    "channel",
                    "published",
                    "views",
                    "likes",
                    "comment_count"
                )
            },
            "comments_scraped": len(df)
        })

        say(
            0.52 + 0.35 * ((i + 1) / len(videos)),
            f"Processed {i + 1}/{len(videos)} videos "
            f"({used} comments analyzed)..."
        )

    if not frames:
        say(0.90, "No comments available to process.")
        return pd.DataFrame(), pd.DataFrame(), notes

    say(0.92, "Classifying comment types...")

    comments_df = add_comment_types(
        pd.concat(frames, ignore_index=True)
    )

    comments_df.insert(0, "niche", niche)
    comments_df.insert(0, "brand", brand)

    say(0.97, "Preparing results for database storage...")

    return comments_df, pd.DataFrame(kept), notes


def save_csv(
    df: pd.DataFrame,
    brand: str,
    folder: str = "data"
) -> str:
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(
        folder,
        f"{slugify(brand)}_comments.csv"
    )

    df.to_csv(path, index=False, encoding="utf-8-sig")

    return path
