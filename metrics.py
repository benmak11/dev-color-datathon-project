"""Aggregate the per-video rows from `prep` into the five tables everything else reads.

`build_tables()` is the only entry point. It returns plain JSON-safe dicts and
lists. No pandas, no custom classes. The Streamlit screens, the tool layer and
the language model all consume the same object.

Two rules the numbers depend on:

*Medians, never means.* Views are brutally skewed (mean 1,029,213 vs median
82,500), so any average is defined by whichever video went viral hardest.

*Three gates, applied in order.* A creator is promising if they posted at least
2 videos in this batch, hold a median of 50,000+ views, and score above the
batch median. The reach floor is a business-relevance filter, not a correction
for small-account inflation. Engagement rate is flat across view quintiles, so
there is no such inflation to correct.

Run `python metrics.py` for a readable summary of the funnel and the tables.
"""

import statistics
from collections import Counter
from datetime import datetime

import prep

GATE_MIN_VIDEOS = 2
GATE_MIN_MEDIAN_VIEWS = 50_000

SHORTLIST_PREVIEW_ROWS = 6
TOP_HASHTAGS_SHOWN = 5

# Dimensions the Q&A layer can segment by. duration_bucket reuses duration_table.
TWO_GROUP_DIMENSIONS = ("verified", "music_is_original")


def _median(values):
    return statistics.median(values)


def build_creator_table(videos):
    """One row per creator, aggregated with medians, sorted by score descending."""
    videos_by_creator = {}
    for video in videos:
        videos_by_creator.setdefault(video["author_name"], []).append(video)

    creators = []
    for handle, creator_videos in videos_by_creator.items():
        hashtags = [v["primary_hashtag"] for v in creator_videos if v["primary_hashtag"]]
        most_common_hashtag = Counter(hashtags).most_common(1)
        scores = [v["score"] for v in creator_videos]

        creators.append(
            {
                "handle": handle,
                "n_videos": len(creator_videos),
                "median_views": _median([v["views"] for v in creator_videos]),
                "total_views": sum(v["views"] for v in creator_videos),
                "best_video_views": max(v["views"] for v in creator_videos),
                "median_score": _median(scores),
                "score_min": min(scores),
                "score_max": max(scores),
                "median_engagement_rate": _median(
                    [v["engagement_rate"] for v in creator_videos]
                ),
                "median_like_rate": _median([v["like_rate"] for v in creator_videos]),
                "median_comment_rate": _median(
                    [v["comment_rate"] for v in creator_videos]
                ),
                "median_share_rate": _median([v["share_rate"] for v in creator_videos]),
                "verified": any(v["author_verified"] for v in creator_videos),
                "top_hashtag": most_common_hashtag[0][0] if most_common_hashtag else None,
            }
        )

    creators.sort(key=lambda creator: creator["median_score"], reverse=True)
    return creators


def build_shortlist(creator_table, batch_median_score, total_views_in_batch):
    """Apply the three gates in order and split qualifiers into evidence tiers.

    The tiers exist because the raw top of the ranking is dominated by creators
    with exactly two videos. Splitting Proven (3+) from Emerging (2) turns the
    thinnest-evidence cohort from a hidden weakness into a stated priority order.
    """
    repeat_creators = [c for c in creator_table if c["n_videos"] >= GATE_MIN_VIDEOS]
    clearing_reach_floor = [
        c for c in repeat_creators if c["median_views"] >= GATE_MIN_MEDIAN_VIEWS
    ]
    qualifying = [
        c for c in clearing_reach_floor if c["median_score"] > batch_median_score
    ]

    proven = [c for c in qualifying if c["n_videos"] >= 3]
    emerging = [c for c in qualifying if c["n_videos"] == GATE_MIN_VIDEOS]
    qualifying_total_views = sum(c["total_views"] for c in qualifying)

    return {
        "gates": {
            "min_videos": GATE_MIN_VIDEOS,
            "min_median_views": GATE_MIN_MEDIAN_VIEWS,
            "score_above": batch_median_score,
        },
        "funnel": {
            "creators": len(creator_table),
            "with_2plus": len(repeat_creators),
            "clearing_reach_floor": len(clearing_reach_floor),
            "qualifying": len(qualifying),
        },
        "proven": proven,
        "emerging": emerging,
        "total_qualifying": len(qualifying),
        "proven_count": len(proven),
        "verified_qualifying": sum(1 for c in qualifying if c["verified"]),
        "qualifying_total_views": qualifying_total_views,
        "qualifying_share_of_total_views": qualifying_total_views / total_views_in_batch,
    }


def build_duration_table(videos):
    """Median engagement and reach per duration bucket, in ascending length order."""
    rows = []
    for bucket in prep.BUCKET_ORDER:
        bucket_videos = [v for v in videos if v["duration_bucket"] == bucket]
        rows.append(
            {
                "bucket": bucket,
                "n_videos": len(bucket_videos),
                "median_views": _median([v["views"] for v in bucket_videos]),
                "median_engagement_rate": _median(
                    [v["engagement_rate"] for v in bucket_videos]
                ),
                "median_score": _median([v["score"] for v in bucket_videos]),
            }
        )
    return rows


def _segment_rows(videos, dimension):
    """Two rows (True/False) for a boolean dimension, each carrying its own n."""
    rows = []
    for group_value in (True, False):
        group_videos = [v for v in videos if v[dimension] is group_value]
        rows.append(
            {
                "group": group_value,
                "n_videos": len(group_videos),
                "share_of_videos": len(group_videos) / len(videos),
                "median_views": _median([v["views"] for v in group_videos]),
                "median_engagement_rate": _median(
                    [v["engagement_rate"] for v in group_videos]
                ),
                "median_score": _median([v["score"] for v in group_videos]),
                "median_like_rate": _median([v["like_rate"] for v in group_videos]),
            }
        )
    return _attach_ratios(rows)


def _attach_ratios(rows):
    """Precompute each group's multiple of the other, so no consumer ever divides.

    The narration layer must not do arithmetic, so "7.6x" has to arrive as a
    string that was computed here.
    """
    metrics = (
        "median_views",
        "median_engagement_rate",
        "median_score",
        "median_like_rate",
    )
    first_row, second_row = rows
    for row, other_row in ((first_row, second_row), (second_row, first_row)):
        row["ratios"] = {
            metric: _ratio(row[metric], other_row[metric])
            for metric in metrics
            if other_row[metric]
        }
    return rows


def _ratio(value, other_value):
    """A multiple plus its display text, with enough precision to keep direction visible.

    One decimal place is fine for 7.6x but rounds 0.96x to "1.0x", which would let
    a narration say verified creators score the same when they in fact score lower.
    Ratios near 1 therefore get two decimals.
    """
    multiple = value / other_value
    decimals = 2 if 0.5 < multiple < 2 else 1
    return {"value": multiple, "text": f"{multiple:.{decimals}f}x"}


def build_dataset_facts(videos, batch_median_score):
    views = [v["views"] for v in videos]
    total_engagements = sum(
        v["likes"] + v["comments"] + v["shares"] for v in videos
    )
    hashtags = [v["primary_hashtag"] for v in videos if v["primary_hashtag"]]

    return {
        "rows": len(videos),
        "creators": len({v["author_name"] for v in videos}),
        "date_min": min(v["upload_date"] for v in videos),
        "date_max": max(v["upload_date"] for v in videos),
        "total_views": sum(views),
        "median_views": _median(views),
        "max_views": max(views),
        "median_engagement_rate": _median([v["engagement_rate"] for v in videos]),
        "likes_share_of_engagement": sum(v["likes"] for v in videos) / total_engagements,
        "batch_median_score": batch_median_score,
        "distinct_hashtags": len(set(hashtags)),
        "blank_hashtags": len(videos) - len(hashtags),
        # Named on screen to justify not segmenting by topic: the most common
        # tags are discovery tags, not themes. Counted here so the caption
        # never hardcodes them.
        "top_hashtags": Counter(hashtags).most_common(TOP_HASHTAGS_SHOWN),
        "duration_convention": prep.DURATION_CONVENTION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_tables(videos=None):
    """Build every aggregate once. The single object all downstream code reads."""
    if videos is None:
        videos = prep.load_rows()

    batch_median_score = _median([v["score"] for v in videos])
    creator_table = build_creator_table(videos)
    duration_table = build_duration_table(videos)

    return {
        "dataset_facts": build_dataset_facts(videos, batch_median_score),
        "creator_table": creator_table,
        "shortlist": build_shortlist(
            creator_table, batch_median_score, sum(v["views"] for v in videos)
        ),
        "duration_table": duration_table,
        "segment_tables": {
            "verified": _segment_rows(videos, "author_verified"),
            "music_is_original": _segment_rows(videos, "music_is_original"),
            "duration_bucket": duration_table,
        },
    }


def summarise(tables):
    """Human-readable dump of the funnel and tables, for eyeballing before Phase 3."""
    facts = tables["dataset_facts"]
    shortlist = tables["shortlist"]
    funnel = shortlist["funnel"]
    verified_rows = tables["segment_tables"]["verified"]
    verified_row, unverified_row = verified_rows

    lines = [
        f"metrics.py: aggregate tables from {facts['rows']:,} videos",
        "",
        "  FUNNEL   "
        f"{funnel['creators']} {funnel['with_2plus']} "
        f"{funnel['clearing_reach_floor']} {funnel['qualifying']}",
        f"    {funnel['creators']:>3} creators",
        f"    {funnel['with_2plus']:>3} with {GATE_MIN_VIDEOS}+ videos in this batch",
        f"    {funnel['clearing_reach_floor']:>3} also clearing "
        f"{GATE_MIN_MEDIAN_VIEWS:,} median views",
        f"    {funnel['qualifying']:>3} also scoring above the batch median  <- the shortlist",
        "",
        f"  batch_median_score={facts['batch_median_score']:.4f}"
        f"   proven={shortlist['proven_count']}"
        f"   emerging={len(shortlist['emerging'])}"
        f"   verified_qualifying={shortlist['verified_qualifying']}",
        f"  qualifying creators hold {shortlist['qualifying_total_views']:,} views"
        f" ({shortlist['qualifying_share_of_total_views']:.1%} of the batch)",
        "",
        "  DURATION   "
        + " ".join(str(row["n_videos"]) for row in tables["duration_table"]),
    ]

    for row in tables["duration_table"]:
        lines.append(
            f"    {row['bucket']:<7} n={row['n_videos']:>3}"
            f"   median views {int(row['median_views']):>7,}"
            f"   median ER {row['median_engagement_rate']:.4f}"
            f"   median score {row['median_score']:.3f}"
        )

    lines += [
        "",
        "  VERIFIED",
        f"    verified     n={verified_row['n_videos']:>3}"
        f"   median views {int(verified_row['median_views']):>7,}"
        f"   median score {verified_row['median_score']:.3f}"
        f"   like rate {verified_row['median_like_rate']:.3f}",
        f"    unverified   n={unverified_row['n_videos']:>3}"
        f"   median views {int(unverified_row['median_views']):>7,}"
        f"   median score {unverified_row['median_score']:.3f}"
        f"   like rate {unverified_row['median_like_rate']:.3f}",
        f"    verified take {verified_row['ratios']['median_views']['text']} the views"
        f" but score {verified_row['ratios']['median_score']['text']} (i.e. lower)"
        ". Scale, not conversation.",
        "",
        f"  SHORTLIST  top {SHORTLIST_PREVIEW_ROWS} of each tier",
    ]

    for tier in ("proven", "emerging"):
        for creator in shortlist[tier][:SHORTLIST_PREVIEW_ROWS]:
            lines.append(
                (
                    f"    {tier:<8} {creator['handle']:<22}"
                    f" n={creator['n_videos']:<2}"
                    f" median views {int(creator['median_views']):>8,}"
                    f" score {creator['median_score'] * 100:>5.1f}"
                    f" {'verified' if creator['verified'] else ''}"
                ).rstrip()
            )

    return "\n".join(lines)


if __name__ == "__main__":
    print(summarise(build_tables()))
