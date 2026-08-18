"""The export itself: shape, uniqueness, totals, and internal consistency."""

from collections import defaultdict

from tests import expectations as expect
from tests.runner import check


def check_all(videos):
    check("row count", len(videos) == expect.ROWS, f"got {len(videos)}")
    check(
        "video_id is unique",
        len({v["video_id"] for v in videos}) == expect.ROWS,
        "duplicate video_id present",
    )

    creators = {v["author_name"] for v in videos}
    check("creator count", len(creators) == expect.CREATORS, f"got {len(creators)}")

    check(
        "no zero-view videos",
        min(v["views"] for v in videos) > 0,
        "a zero would make every rate undefined",
    )

    total_views = sum(v["views"] for v in videos)
    check("total views", total_views == expect.TOTAL_VIEWS, f"got {total_views:,}")

    date_range = (
        min(v["upload_date"] for v in videos),
        max(v["upload_date"] for v in videos),
    )
    check("date range", date_range == expect.DATE_RANGE, f"got {date_range}")

    verified_by_creator = defaultdict(set)
    for video in videos:
        verified_by_creator[video["author_name"]].add(video["author_verified"])
    inconsistent = [h for h, flags in verified_by_creator.items() if len(flags) > 1]
    check(
        "author_verified is constant per creator",
        not inconsistent,
        f"{len(inconsistent)} creators disagree with themselves",
    )
