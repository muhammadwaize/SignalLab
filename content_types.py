"""
Guess what kind of post a video is (Table A of Project 3: content_type, campaign) from its title,
and how old it is. Keyword based: add or change words in CONTENT_TYPES below.
"""

import re
from datetime import date, datetime

CONTENT_TYPES = [
    ("Unboxing / haul", r"unbox|\bhaul\b|first look|what i (?:got|bought|ordered)"),
    ("Sale announcement", r"\bsale\b|discount|% ?off|\boffers?\b|\bdeals?\b|clearance|11\.?11|12\.?12|black friday|flash"),
    ("Eid / festive campaign", r"\beid\b|festive|ramadan|ramzan|shaadi|wedding|bridal"),
    ("Review", r"review|honest|opinion|\bworth\b|\bvs\.?\b|comparison|\btest(?:ed|ing|s)?\b|rating|ranked"),
    ("Styling / lookbook", r"styl(?:e|ing|ed)|lookbook|ootd|\boutfits?\b|try[- ]?on|get ready|\blooks?\b"),
    ("Advert / campaign", r"\bad\b|advert|commercial|campaign|tvc|official|launch|teaser|trailer"),
    ("Influencer / vlog", r"vlog|influencer|behind the scenes|\bbts\b|diaries|shoot|day in my life"),
]
CAMPAIGNS = [
    ("11.11 / 12.12", r"11\.?11|12\.?12"),
    ("Eid collection", r"\beid\b"),
    ("Sale", r"\bsale\b|discount|% ?off"),
    ("Collection / season", r"collection|lawn|winter|summer|spring"),
]

_types = [(name, re.compile(p, re.IGNORECASE)) for name, p in CONTENT_TYPES]
_campaigns = [(name, re.compile(p, re.IGNORECASE)) for name, p in CAMPAIGNS]


def classify(title: str, brand: str = "") -> tuple:
    """Returns (content_type, campaign) guessed from the title. The brand name is removed first, so a brand
    called 'Outfitters' is not mistaken for the word 'outfit'."""
    title = str(title or "")
    tokens = re.findall(r"[a-z0-9]+", str(brand).lower())
    if tokens:
        title = re.sub(r"\b" + r"[\W_]+".join(map(re.escape, tokens)) + r"\b", " ", title, flags=re.IGNORECASE)
    content = next((name for name, rx in _types if rx.search(title)), "Other")
    campaign = next((name for name, rx in _campaigns if rx.search(title)), "General")
    return content, campaign


def days_since(published) -> int | None:
    """Days between a 'YYYY-MM-DD' publish date and today (None if the date is unknown)."""
    try:
        return (date.today() - datetime.strptime(str(published)[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return None
