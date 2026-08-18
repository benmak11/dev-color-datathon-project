"""Load the trending-TikTok export and derive per-video engagement metrics.

Duration buckets are lower-bound inclusive and upper-bound exclusive, with the
last bucket closed: 4-9s, 10-19s, 20-29s, 30-60s. That convention is what makes
"169 videos run 30s or longer" true. It is quotable on screen as-is.

Engagement is 96.8% likes in this batch, so a raw like+comment+share rate is a
like rate in disguise. Each rate is percentile-ranked separately and the three
ranks are averaged. That blend is `score`.

Run `python prep.py` for a readable summary of what was loaded.
"""

import csv
import statistics
from collections import Counter
from core.paths import DATA_FILE

DATA_PATH = DATA_FILE

INTEGER_COLUMNS = ("views", "likes", "comments", "shares", "duration_sec")
BOOLEAN_COLUMNS = ("author_verified", "music_is_original")
NULLABLE_TEXT_COLUMNS = ("primary_hashtag", "caption")

# Each engagement rate gets its own percentile column; `score` averages the three.
RATE_TO_PERCENTILE_COLUMN = {
    "like_rate": "p_like",
    "comment_rate": "p_comment",
    "share_rate": "p_share",
}

BUCKET_ORDER = ("4-9s", "10-19s", "20-29s", "30-60s")

DURATION_CONVENTION = (
    "Duration buckets are lower-bound inclusive and upper-bound exclusive "
    "(the last bucket is closed): 4-9s, 10-19s, 20-29s, 30-60s."
)


def percentile_rank(values):
    """Percentile-rank `values` into [0, 1], averaging the rank within tie groups.

    Comment and share rates tie often, so tied videos must share a rank rather
    than being split by input order. A tied lowest group therefore averages
    slightly above 0.0. That is correct, not a bug.
    """
    value_count = len(values)
    indices_low_to_high = sorted(range(value_count), key=lambda index: values[index])
    percentiles = [0.0] * value_count

    tie_group_start = 0
    while tie_group_start < value_count:
        tie_group_end = tie_group_start
        while (
            tie_group_end + 1 < value_count
            and values[indices_low_to_high[tie_group_end + 1]]
            == values[indices_low_to_high[tie_group_start]]
        ):
            tie_group_end += 1

        average_position = (tie_group_start + tie_group_end) / 2
        shared_percentile = average_position / (value_count - 1)
        for position in range(tie_group_start, tie_group_end + 1):
            percentiles[indices_low_to_high[position]] = shared_percentile

        tie_group_start = tie_group_end + 1

    return percentiles


def duration_bucket(duration_seconds):
    if duration_seconds < 10:
        return "4-9s"
    if duration_seconds < 20:
        return "10-19s"
    if duration_seconds < 30:
        return "20-29s"
    return "30-60s"


def load_rows(path=DATA_PATH):
    """Return one dict per video, typed and with all derived fields attached."""
    with open(path, newline="", encoding="utf-8") as csv_file:
        videos = list(csv.DictReader(csv_file))

    for video in videos:
        for column in INTEGER_COLUMNS:
            video[column] = int(video[column])
        for column in BOOLEAN_COLUMNS:
            video[column] = video[column] == "True"
        for column in NULLABLE_TEXT_COLUMNS:
            video[column] = video[column] or None

        views = video["views"]
        video["like_rate"] = video["likes"] / views
        video["comment_rate"] = video["comments"] / views
        video["share_rate"] = video["shares"] / views
        video["engagement_rate"] = (
            video["likes"] + video["comments"] + video["shares"]
        ) / views
        video["duration_bucket"] = duration_bucket(video["duration_sec"])

    for rate_column, percentile_column in RATE_TO_PERCENTILE_COLUMN.items():
        percentiles = percentile_rank([video[rate_column] for video in videos])
        for video, percentile in zip(videos, percentiles):
            video[percentile_column] = percentile

    for video in videos:
        video["score"] = statistics.mean(
            video[percentile_column]
            for percentile_column in RATE_TO_PERCENTILE_COLUMN.values()
        )

    return videos


def summarise(videos):
    """Generate report of what was loaded, for eyeballing before Phase 2."""
    views = [video["views"] for video in videos]
    median_score = statistics.median(video["score"] for video in videos)
    median_engagement = statistics.median(video["engagement_rate"] for video in videos)
    likes_share = sum(video["likes"] for video in videos) / sum(
        video["likes"] + video["comments"] + video["shares"] for video in videos
    )
    bucket_counts = Counter(video["duration_bucket"] for video in videos)
    buckets = " | ".join(f"{name}: {bucket_counts[name]}" for name in BUCKET_ORDER)

    return "\n".join(
        [
            f"prep.py: per-video metrics from {DATA_PATH.name}",
            "",
            f"  videos loaded               {len(videos):,}",
            f"  distinct creators           {len({v['author_name'] for v in videos}):,}",
            f"  verified videos             {sum(v['author_verified'] for v in videos):,}",
            f"  date range                  {min(v['upload_date'] for v in videos)} to {max(v['upload_date'] for v in videos)}",
            "",
            f"  views  min / median / max   {min(views):,} / {int(statistics.median(views)):,} / {max(views):,}",
            f"  engagement rate (median)    {median_engagement:.4f}  ({likes_share:.1%} of engagement is likes)",
            f"  blended score (median)      {median_score:.4f}  <- batch_median_score gate for metrics.py",
            "",
            f"  duration buckets            {buckets}",
            f"  missing hashtags            {sum(1 for v in videos if v['primary_hashtag'] is None):,}",
            "",
            f"  {DURATION_CONVENTION}",
        ]
    )


if __name__ == "__main__":
    print(summarise(load_rows()))
