"""
Find YouTube videos for a brand.

* With a YouTube Data API key  -> official search + real views / likes / comment counts.
* Without a key                -> falls back to yt-dlp search (python -m pip install yt-dlp).
"""

import html as html_lib
import re

import requests

API = "https://www.googleapis.com/youtube/v3"


def _tokens(text) -> list:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _has_phrase(tokens: list, phrase_tokens: list) -> bool:
    n = len(phrase_tokens)
    return n > 0 and any(tokens[i:i + n] == phrase_tokens for i in range(len(tokens) - n + 1))


def mentions_brand(video: dict, brand: str) -> bool:
    """The brand must appear as WHOLE words ('J.' matches 'by J. review' but not 'Janan'), or, for longer names,
    written as one word ('GulAhmed')."""
    brand_tokens = _tokens(brand)
    if not brand_tokens:
        return False
    joined = "".join(brand_tokens)
    for key in ("title", "channel", "description"):
        tokens = _tokens(video.get(key, ""))
        if _has_phrase(tokens, brand_tokens) or (len(joined) >= 5 and joined in "".join(tokens)):
            return True
    return False


def has_excluded(video: dict, words: list) -> bool:
    """True if the title, channel or description contains any of the words to leave out (whole words)."""
    for word in words:
        phrase = _tokens(word)
        if phrase and any(_has_phrase(_tokens(video.get(k, "")), phrase) for k in ("title", "channel", "description")):
            return True
    return False


def build_queries(brand: str, niche: str = "", region: str = "") -> list[str]:
    base = [
        f"{brand} review",
        f"{brand} unboxing",
        f"{brand} {niche}".strip() if niche else f"{brand} ad",
        brand,
        f"{brand} price",
    ]
    candidates = [f"{q} {region}".strip() for q in base] if region else base
    seen, out = set(), []
    for q in candidates:
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def _api_error(r: requests.Response) -> str:
    try:
        msg = r.json()["error"]["message"]
    except Exception:
        msg = r.text[:200]
    return f"HTTP {r.status_code}: {msg}"


def _api_search(query: str, n: int, key: str) -> list[dict]:
    r = requests.get(
        f"{API}/search",
        params={"part": "snippet", "q": query, "type": "video", "maxResults": min(n, 50), "key": key},
        timeout=25,
    )
    if r.status_code != 200:
        raise RuntimeError(_api_error(r))
    out = []
    for item in r.json().get("items", []):
        vid = (item.get("id") or {}).get("videoId")
        if not vid:
            continue
        sn = item.get("snippet", {})
        out.append({
            "video_id": vid,
            "title": html_lib.unescape(sn.get("title", "")),
            "channel": html_lib.unescape(sn.get("channelTitle", "")),
            "published": str(sn.get("publishedAt", ""))[:10],
            "description": html_lib.unescape(sn.get("description", "")),
        })
    return out


def _api_stats(ids: list[str], key: str) -> dict:
    stats = {}
    for i in range(0, len(ids), 50):
        r = requests.get(
            f"{API}/videos",
            params={"part": "statistics", "id": ",".join(ids[i:i + 50]), "key": key},
            timeout=25,
        )
        if r.status_code != 200:
            continue
        for item in r.json().get("items", []):
            s = item.get("statistics", {})
            stats[item["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comment_count": int(s.get("commentCount", 0)),
            }
    return stats


def _ytdlp_search(query: str, n: int) -> list[dict]:
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError(
            "No working YouTube API key and yt-dlp is not installed. "
            "Run:  python -m pip install yt-dlp   (or add a YouTube API key)."
        )
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    out = []
    for e in (info or {}).get("entries", []) or []:
        if not e or not e.get("id"):
            continue
        out.append({
            "video_id": e["id"],
            "title": e.get("title") or "",
            "channel": e.get("channel") or e.get("uploader") or "",
            "published": "",
            "description": e.get("description") or "",
            "views": int(e.get("view_count") or 0),
        })
    return out


def search_videos(brand: str, niche: str = "", max_videos: int = 10, api_key: str = "", strict: bool = True,
                  exclude: list | None = None, region: str = ""):
    """Returns (videos, mode, notes). Each video is a dict with video_id, title, channel, views, likes ..."""
    notes = []
    found: dict[str, dict] = {}
    use_api = bool(api_key)
    exclude = [w.strip() for w in (exclude or []) if w and w.strip()]
    skipped_ids: set = set()

    for query in build_queries(brand, niche, region):
        if len(found) >= max_videos:
            break
        want = min(50, max(10, max_videos * 2))
        results = None
        if use_api:
            try:
                results = _api_search(query, want, api_key)
            except RuntimeError as e:
                notes.append(f"YouTube API search failed ({e}). Switched to yt-dlp.")
                use_api = False
        if results is None:
            results = _ytdlp_search(query, want)

        for v in results:
            if v["video_id"] in found:
                continue
            if strict and not mentions_brand(v, brand):
                continue
            if exclude and has_excluded(v, exclude):
                skipped_ids.add(v["video_id"])
                continue
            found[v["video_id"]] = v
            if len(found) >= max_videos:
                break

    videos = list(found.values())[:max_videos]
    if use_api and videos:
        stats = _api_stats([v["video_id"] for v in videos], api_key)
        for v in videos:
            v.update(stats.get(v["video_id"], {}))
    for v in videos:
        for k in ("views", "likes", "comment_count"):
            v.setdefault(k, 0)
        v.setdefault("published", "")

    if skipped_ids:
        notes.append(f"Left out {len(skipped_ids)} video(s) because they matched your exclude words ({', '.join(exclude)}).")
    return videos, ("YouTube API" if use_api else "yt-dlp"), notes
