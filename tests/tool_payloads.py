"""Every tool returns the same envelope, and `n` is never silently missing.

Sample size is the honesty mechanism: "9 creators" and "9 of 45" read very
differently. If `n` can arrive null, the narration layer can drop it.
"""

from core import tools
from tests import expectations as expect
from tests.runner import check


def check_all(tables):
    check(
        "five tools are registered",
        len(tools.REGISTRY) == 5,
        f"got {sorted(tools.REGISTRY)}",
    )
    check(
        "every tool has a schema",
        {schema["name"] for schema in tools.SCHEMAS} == set(tools.REGISTRY),
        "schemas and registry disagree",
    )

    payloads = {
        "top_creators": tools.top_creators(),
        "top_creators_wide": tools.top_creators(qualifying_only=False),
        "creator_profile": tools.creator_profile("papaswolio"),
        "creator_profile_missing": tools.creator_profile("nobody-at-all"),
        "metric_by_segment": tools.metric_by_segment("median_views", "verified"),
        "dataset_facts": tools.dataset_facts(),
        "cannot_answer": tools.cannot_answer("no follower counts"),
    }

    for label, payload in payloads.items():
        for field in ("tool", "filters", "n", "unit", "rows", "notes"):
            check(
                f"{label} payload has {field}",
                field in payload,
                f"missing {field}",
            )
        check(
            f"{label} carries the scope note",
            any("already trended" in note for note in payload["notes"]),
            "scope must ride on every payload",
        )
        if label not in ("cannot_answer", "creator_profile_missing"):
            check(
                f"{label} reports a positive sample size",
                isinstance(payload["n"], int) and payload["n"] > 0,
                f"n = {payload['n']!r}",
            )

    shortlist_total = tables["shortlist"]["total_qualifying"]
    check(
        "top_creators defaults match the shortlist on screen",
        payloads["top_creators"]["n"] == shortlist_total,
        f"tool says {payloads['top_creators']['n']}, screen says {shortlist_total}",
    )
    check(
        "widening past the score gate returns more creators",
        payloads["top_creators_wide"]["n"]
        == tables["shortlist"]["funnel"]["clearing_reach_floor"],
        f"got {payloads['top_creators_wide']['n']}",
    )
    check(
        "metric_by_segment ships ratio text so the model never divides",
        payloads["metric_by_segment"]["ratio_text"] == expect.VERIFIED_VIEWS_RATIO,
        f"got {payloads['metric_by_segment'].get('ratio_text')!r}",
    )
    check(
        "a missing handle returns suggestions, not an exception",
        payloads["creator_profile_missing"]["error"] == "not_found",
        "expected a not_found envelope",
    )
    check(
        "creator_profile names the failing gate when one fails",
        tools.creator_profile("cainguzman")["rows"][0]["tier"].startswith(
            "Did not qualify"
        ),
        "a non-qualifying creator must say which bar it missed",
    )
