"""The ranking that the whole engagement score rests on.

The lesson recorded here: an invariant that only inspects a property of the
output is weaker than one that recomputes the output. The tie check alone
passed a wrong percentile on a video whose rate was unique.
"""

from collections import defaultdict

from core import prep
from tests import expectations as expect
from tests.runner import check


def check_all(videos):
    for column in expect.PERCENTILE_COLUMNS:
        values = [v[column] for v in videos]
        check(
            f"{column} within [0, 1]",
            all(0.0 <= value <= 1.0 for value in values),
            f"range {min(values)} to {max(values)}",
        )

    # Deliberately NOT asserting min == 0.0. With average-rank ties, a tied
    # lowest group averages above zero (p_comment bottoms out at 0.0040), so an
    # exact-zero floor would fail on correct code.
    for rate_column, percentile_column in prep.RATE_TO_PERCENTILE_COLUMN.items():
        percentiles_by_rate = defaultdict(set)
        for video in videos:
            percentiles_by_rate[video[rate_column]].add(video[percentile_column])
        split_ties = {
            rate: seen for rate, seen in percentiles_by_rate.items() if len(seen) > 1
        }
        check(
            f"{percentile_column} ties share a rank",
            not split_ties,
            f"{len(split_ties)} rate values were split across ranks",
        )

        recomputed = prep.percentile_rank([v[rate_column] for v in videos])
        mismatches = sum(
            1
            for video, expected in zip(videos, recomputed)
            if abs(video[percentile_column] - expected) > 1e-12
        )
        check(
            f"{percentile_column} matches a recompute from {rate_column}",
            not mismatches,
            f"{mismatches} of {len(videos)} percentiles disagree",
        )
