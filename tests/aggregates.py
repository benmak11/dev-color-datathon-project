"""Everything `build_tables` produces: scores, buckets, creators, the funnel."""

import statistics

from core import metrics
from tests import expectations as expect
from tests.runner import check


def check_scores(videos, tables):
    computed_median = statistics.median(v["score"] for v in videos)
    stored_median = tables["dataset_facts"]["batch_median_score"]
    check(
        "batch_median_score matches the videos it came from",
        abs(computed_median - stored_median) < 1e-9,
        f"{computed_median} vs {stored_median}",
    )
    check(
        "batch_median_score is the expected value",
        round(stored_median, 4) == expect.BATCH_MEDIAN_SCORE,
        f"got {stored_median:.4f}",
    )


def check_duration_table(tables):
    counts = tuple(row["n_videos"] for row in tables["duration_table"])
    check("duration bucket counts", counts == expect.DURATION_COUNTS, f"got {counts}")
    check(
        "duration buckets cover every video",
        sum(counts) == expect.ROWS,
        f"buckets hold {sum(counts)}",
    )


def check_creator_table(tables):
    creator_table = tables["creator_table"]
    check(
        "one row per creator",
        len(creator_table) == expect.CREATORS,
        f"got {len(creator_table)}",
    )
    check(
        "every creator has at least one video",
        all(c["n_videos"] >= 1 for c in creator_table),
        "a creator with zero videos means the grouping is broken",
    )
    check(
        "every creator has positive median views",
        all(c["median_views"] > 0 for c in creator_table),
        "zero median views would break the reach gate",
    )
    check(
        "creator scores within [0, 1]",
        all(0.0 <= c["median_score"] <= 1.0 for c in creator_table),
        "score is an average of percentiles and cannot leave [0, 1]",
    )
    check(
        "video counts sum to the batch",
        sum(c["n_videos"] for c in creator_table) == expect.ROWS,
        "a video was dropped or double-counted during grouping",
    )


def check_funnel_and_shortlist(tables):
    shortlist = tables["shortlist"]
    funnel = tuple(shortlist["funnel"].values())

    check("funnel", funnel == expect.FUNNEL, f"got {funnel}")
    check(
        "funnel never widens",
        all(earlier >= later for earlier, later in zip(funnel, funnel[1:])),
        f"got {funnel}",
    )
    check(
        "gates are the documented ones",
        shortlist["gates"]["min_videos"] == 2
        and shortlist["gates"]["min_median_views"] == 50_000,
        f"got {shortlist['gates']}",
    )
    check(
        "proven tier is 3+ videos",
        all(c["n_videos"] >= 3 for c in shortlist["proven"]),
        "a 2-video creator reached the proven tier",
    )
    check(
        "emerging tier is exactly 2 videos",
        all(c["n_videos"] == 2 for c in shortlist["emerging"]),
        "the emerging tier is meant to be the thin-evidence cohort",
    )
    check(
        "tiers account for every qualifier",
        len(shortlist["proven"]) + len(shortlist["emerging"])
        == shortlist["total_qualifying"],
        "a qualifier fell between the tiers",
    )
    check(
        "proven count",
        shortlist["proven_count"] == expect.PROVEN_COUNT,
        f"got {shortlist['proven_count']}",
    )
    check(
        "verified qualifiers",
        shortlist["verified_qualifying"] == expect.VERIFIED_QUALIFYING,
        f"got {shortlist['verified_qualifying']}",
    )
    check(
        "every qualifier clears all three gates",
        all(
            c["n_videos"] >= 2
            and c["median_views"] >= 50_000
            and c["median_score"] > tables["dataset_facts"]["batch_median_score"]
            for c in shortlist["proven"] + shortlist["emerging"]
        ),
        "a creator on the shortlist does not pass the gates",
    )


def check_no_means_on_display(tables):
    """Views are skewed enough that a mean anywhere near a screen is a defect."""
    mean_keys = [key for key in tables["dataset_facts"] if "mean" in key.lower()]
    check(
        "no mean in dataset_facts",
        not mean_keys,
        f"found {mean_keys}. Median 82,500 vs mean 1,029,213 is why.",
    )


def check_segment_ratios(tables):
    """Ratio text must keep direction visible; 0.96x must not render as 1.0x."""
    for dimension in metrics.TWO_GROUP_DIMENSIONS:
        key = "verified" if dimension == "verified" else dimension
        for row in tables["segment_tables"][key]:
            for metric_name, ratio in row["ratios"].items():
                near_parity = 0.5 < ratio["value"] < 2
                decimals = len(ratio["text"].rstrip("x").split(".")[-1])
                check(
                    f"{key}/{metric_name} ratio text precision",
                    decimals == (2 if near_parity else 1),
                    f"{ratio['value']} rendered as {ratio['text']}",
                )


def check_all(videos, tables):
    check_scores(videos, tables)
    check_duration_table(tables)
    check_creator_table(tables)
    check_funnel_and_shortlist(tables)
    check_no_means_on_display(tables)
    check_segment_ratios(tables)
