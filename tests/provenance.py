"""The guard must pass real prose and catch the fabrication we actually saw."""

from core import tools
from core.provenance import normalise, payload_numbers, provenance_check
from tests.runner import check


def check_all(tables):
    facts = tools.REGISTRY["dataset_facts"]()
    check(
        "provenance passes figures drawn from the payload",
        provenance_check("There are 802 creators in 1,000 videos.", facts)[0],
        "a legitimate sentence was rejected",
    )
    check(
        "provenance catches an invented figure",
        provenance_check("There are 803 creators.", facts) == (False, ["803"]),
        "a wrong number slipped through",
    )

    segment = tools.REGISTRY["metric_by_segment"](
        metric="median_views", dimension="verified"
    )
    # The live model wrote this. The multiple is its own arithmetic, and no
    # amount of prompt instruction stopped it.
    ok, unbacked = provenance_check(
        "verified creators show 11.7% versus 8.7%, a 1.33x difference.", segment
    )
    check(
        "provenance catches the multiple the model computed itself",
        not ok and "1.33" in unbacked,
        f"got {unbacked}",
    )
    check(
        "rates are not auto-expanded into percentages",
        normalise("11.7") in payload_numbers(segment),
        "display strings should supply the readable form, not an expansion rule",
    )
    check(
        "date digits in payload strings are allowed",
        provenance_check("Covers 22 Sep to 21 Dec 2020.", facts)[0],
        "dates come from the payload's own strings",
    )
