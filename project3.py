"""Project 3 analytics: comment-derived audience clusters and unusual-post detection.

Clusters describe patterns in collected comments, not unique people. The project
schema does not retain commenter identities, so this module deliberately avoids
claiming person-level audience segmentation.
"""

from collections import Counter
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

import db

NOT_AVAILABLE = "Not available"


def _mode(series: pd.Series) -> str:
    values = series.fillna("").astype(str)
    values = values[values.str.strip() != ""]
    return values.value_counts().index[0] if not values.empty else NOT_AVAILABLE


def _cluster_label(row: dict) -> tuple[str, str]:
    """Create a readable, evidence-based label and description for a cluster."""
    purchase = row["purchase_pct"]
    intent = row["intent_pct"]
    positive = row["positive_pct"]
    if purchase >= 20:
        label = "Customers / buyers"
        description = "Comments in this group contain comparatively frequent purchase claims."
    elif intent >= 25:
        label = "High purchase interest"
        description = "This group contains a comparatively high share of comments expressing buying intent."
    elif positive >= 65:
        label = "Positive advocates"
        description = "This group is predominantly positive, with relatively few explicit purchase signals."
    elif row["negative_pct"] >= 45:
        label = "Critical audience"
        description = "This group contains a comparatively high share of negative comments."
    else:
        label = "General discussion"
        description = "This group has a mixed pattern of sentiment and purchase signals."
    return label, description


def cluster_comments(run_id: int, n_clusters: int = 4) -> dict:
    comments = db.load_comments(run_id)
    if len(comments) < 4:
        raise ValueError("At least 4 comments are needed to create audience clusters.")

    # Keep feature engineering transparent and based only on columns already saved in Table B.
    numeric = pd.DataFrame({
        "sentiment": pd.to_numeric(comments["compound"], errors="coerce").fillna(0).clip(-1, 1),
        "purchased": comments["purchased"].astype(int),
        "intent": comments["intent"].astype(int),
        "show_off": comments["show_off"].astype(int),
        "likes_log": np.log1p(pd.to_numeric(comments["likes"], errors="coerce").fillna(0).clip(lower=0)),
        "replies_log": np.log1p(pd.to_numeric(comments["replies"], errors="coerce").fillna(0).clip(lower=0)),
        "reach_weight": pd.to_numeric(comments["weight"], errors="coerce").fillna(1).clip(lower=0),
    })
    categorical = pd.DataFrame({
        "language": comments["language"].fillna("Unknown").replace("", "Unknown"),
        "topic": comments["topics"].fillna("Unknown").replace("", "Unknown"),
        "comment_type": comments["comment_type"].fillna("Unknown").replace("", "Unknown"),
    })
    encoded = pd.get_dummies(categorical, dtype=float)
    scaled = StandardScaler().fit_transform(numeric)
    features = np.hstack([scaled, encoded.to_numpy(dtype=float)])

    k = max(2, min(int(n_clusters), 8, len(comments) - 1))
    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(features)

    working = comments.copy()
    working["cluster_no"] = labels + 1
    profiles, assignments = [], []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for cluster_no, group in working.groupby("cluster_no", sort=True):
        count = len(group)
        positive = float((group["compound"] >= 0.05).mean() * 100)
        negative = float((group["compound"] <= -0.05).mean() * 100)
        purchase = float(group["purchased"].mean() * 100)
        intent = float(group["intent"].mean() * 100)
        profile = {
            "cluster_no": int(cluster_no), "comment_count": int(count),
            "positive_pct": round(positive, 1), "negative_pct": round(negative, 1),
            "purchase_pct": round(purchase, 1), "intent_pct": round(intent, 1),
            "avg_sentiment": round(float(group["compound"].mean()), 3),
            "top_topic": _mode(group["topics"]), "top_language": _mode(group["language"]),
            "top_comment_type": _mode(group["comment_type"]), "created_at": stamp,
        }
        label_text, description = _cluster_label(profile)
        profile["label"] = label_text
        profile["description"] = description
        profiles.append(profile)
        assignments.extend((int(r.id), int(cluster_no)) for r in group.itertuples())

    db.save_cluster_results(run_id, profiles, assignments)
    return {"profiles": profiles, "assignments_count": len(assignments), "n_clusters": k}


def _robust_outlier_mask(values: pd.Series) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if x.notna().sum() < 4 or x.nunique(dropna=True) < 3:
        return pd.Series(False, index=values.index)
    median = x.median()
    mad = (x - median).abs().median()
    if mad and np.isfinite(mad):
        score = 0.6745 * (x - median).abs() / mad
        return score.fillna(0) > 3.5
    q1, q3 = x.quantile(.25), x.quantile(.75)
    iqr = q3 - q1
    if not np.isfinite(iqr):
        return pd.Series(False, index=values.index)
    if iqr == 0:
        return (x.notna() & (x != median))
    return ((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).fillna(False)


def detect_unusual_posts(run_id: int) -> dict:
    videos = db.load_videos(run_id)
    comments = db.load_comments(run_id)
    if len(videos) < 4:
        raise ValueError("At least 4 analysed posts are needed for unusual-post detection.")

    comment_stats = pd.DataFrame()
    if not comments.empty:
        comment_stats = comments.groupby("video_id").agg(
            avg_comment_sentiment=("compound", "mean"),
            purchase_intent_pct=("intent", "mean"),
            purchase_claim_pct=("purchased", "mean"),
            analysed_comments=("id", "count"),
        ).reset_index()
        for col in ("purchase_intent_pct", "purchase_claim_pct"):
            comment_stats[col] *= 100

    frame = videos.copy().rename(columns={"post_id": "video_id"})
    if not comment_stats.empty:
        frame = frame.merge(comment_stats, on="video_id", how="left")
    for col in ("views", "likes", "comments_count", "days_since_post", "comments_scraped",
                "avg_comment_sentiment", "purchase_intent_pct", "purchase_claim_pct"):
        if col not in frame:
            frame[col] = np.nan
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["engagement_rate_pct"] = np.where(
        frame["views"].fillna(0) > 0,
        (frame["likes"].fillna(0) + frame["comments_count"].fillna(0)) / frame["views"] * 100,
        np.nan,
    )

    metrics = ["views", "likes", "comments_count", "days_since_post", "engagement_rate_pct",
               "avg_comment_sentiment", "purchase_intent_pct"]
    flags = {}
    for metric in metrics:
        flags[metric] = _robust_outlier_mask(frame[metric])

    results = []
    for idx, row in frame.iterrows():
        reasons = []
        for metric in metrics:
            if bool(flags[metric].loc[idx]):
                pretty = metric.replace("_", " ")
                value = row[metric]
                if pd.notna(value):
                    reasons.append(f"Unusually high or low {pretty} ({value:.2f})")
        if reasons:
            results.append({
                "video_id": str(row.get("video_id", "")),
                "title": str(row.get("title") or "Untitled post"),
                "channel": str(row.get("channel") or ""),
                "views": int(row["views"]) if pd.notna(row["views"]) else 0,
                "likes": int(row["likes"]) if pd.notna(row["likes"]) else 0,
                "comments_count": int(row["comments_count"]) if pd.notna(row["comments_count"]) else 0,
                "engagement_rate_pct": round(float(row["engagement_rate_pct"]), 3) if pd.notna(row["engagement_rate_pct"]) else None,
                "avg_comment_sentiment": round(float(row["avg_comment_sentiment"]), 3) if pd.notna(row["avg_comment_sentiment"]) else None,
                "purchase_intent_pct": round(float(row["purchase_intent_pct"]), 1) if pd.notna(row["purchase_intent_pct"]) else None,
                "anomaly_count": len(reasons), "reasons": " | ".join(reasons),
                "source_url": str(row.get("source_url") or ""),
                "data_origin": str(row.get("data_origin") or "observed"),
            })

    # Most unusual first; do not invent anomalies if no metric crosses the robust threshold.
    results.sort(key=lambda r: (r["anomaly_count"], r["views"]), reverse=True)
    db.save_unusual_posts(run_id, results)
    return {"posts": results, "posts_checked": int(len(videos)), "flagged_count": len(results)}


def run_project3(run_id: int, n_clusters: int = 4) -> dict:
    cluster_result = cluster_comments(run_id, n_clusters)
    anomaly_result = detect_unusual_posts(run_id)
    return {"clusters": cluster_result, "anomalies": anomaly_result}
