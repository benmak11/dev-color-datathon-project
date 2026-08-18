"""Assert every invariant the brief depends on. Run after every change.

Plain assertions, no pytest. The point is that `python checks.py` is one
command with an obvious exit code, not a test framework to configure.

The expected values below are hardcoded on purpose. This is the file that
catches a number drifting; if an expectation here disagrees with the code, one
of them is wrong and the disagreement is the signal. (The rule against
hardcoded numbers applies to anything displayed to the user, not to the file
whose job is to check the display.)

The source architecture doc claimed a funnel of 802 -> 91 -> 76 -> 47. The real
answer is 74 and 45. That transcription error is why this file exists.
"""

import re
import statistics
import sys
from collections import Counter, defaultdict

import metrics
import prep

EXPECTED_ROWS = 1_000
EXPECTED_CREATORS = 802
EXPECTED_TOTAL_VIEWS = 1_029_212_935
EXPECTED_DATE_RANGE = ("2020-09-22", "2020-12-21")
EXPECTED_FUNNEL = (802, 91, 74, 45)
EXPECTED_DURATION_COUNTS = (203, 517, 111, 169)
EXPECTED_BATCH_MEDIAN_SCORE = 0.4977
EXPECTED_PROVEN_COUNT = 14
EXPECTED_VERIFIED_QUALIFYING = 4

PERCENTILE_COLUMNS = ("p_like", "p_comment", "p_share")

passed_checks = []


def check(label, condition, detail=""):
    """Record a passing check, or fail loudly with the label and what went wrong."""
    assert condition, f"{label}: {detail}"
    passed_checks.append(label)


def check_source_data(videos):
    check("row count", len(videos) == EXPECTED_ROWS, f"got {len(videos)}")
    check(
        "video_id is unique",
        len({v["video_id"] for v in videos}) == EXPECTED_ROWS,
        "duplicate video_id present",
    )

    creators = {v["author_name"] for v in videos}
    check("creator count", len(creators) == EXPECTED_CREATORS, f"got {len(creators)}")

    check(
        "no zero-view videos",
        min(v["views"] for v in videos) > 0,
        "a zero would make every rate undefined",
    )

    total_views = sum(v["views"] for v in videos)
    check("total views", total_views == EXPECTED_TOTAL_VIEWS, f"got {total_views:,}")

    date_range = (
        min(v["upload_date"] for v in videos),
        max(v["upload_date"] for v in videos),
    )
    check("date range", date_range == EXPECTED_DATE_RANGE, f"got {date_range}")

    verified_by_creator = defaultdict(set)
    for video in videos:
        verified_by_creator[video["author_name"]].add(video["author_verified"])
    inconsistent = [h for h, flags in verified_by_creator.items() if len(flags) > 1]
    check(
        "author_verified is constant per creator",
        not inconsistent,
        f"{len(inconsistent)} creators disagree with themselves",
    )


def check_percentiles(videos):
    for column in PERCENTILE_COLUMNS:
        values = [v[column] for v in videos]
        check(
            f"{column} within [0, 1]",
            all(0.0 <= value <= 1.0 for value in values),
            f"range {min(values)}–{max(values)}",
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

        # The tie check alone only catches ties being split; a wrong percentile
        # on a video whose rate is unique passes it. Recomputing from the rates
        # is what actually pins every value in the column.
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
        round(stored_median, 4) == EXPECTED_BATCH_MEDIAN_SCORE,
        f"got {stored_median:.4f}",
    )


def check_duration_table(tables):
    counts = tuple(row["n_videos"] for row in tables["duration_table"])
    check("duration bucket counts", counts == EXPECTED_DURATION_COUNTS, f"got {counts}")
    check(
        "duration buckets cover every video",
        sum(counts) == EXPECTED_ROWS,
        f"buckets hold {sum(counts)}",
    )


def check_creator_table(tables):
    creator_table = tables["creator_table"]
    check(
        "one row per creator",
        len(creator_table) == EXPECTED_CREATORS,
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
        sum(c["n_videos"] for c in creator_table) == EXPECTED_ROWS,
        "a video was dropped or double-counted during grouping",
    )


def check_funnel_and_shortlist(tables):
    shortlist = tables["shortlist"]
    funnel = tuple(shortlist["funnel"].values())

    check("funnel", funnel == EXPECTED_FUNNEL, f"got {funnel}")
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
        shortlist["proven_count"] == EXPECTED_PROVEN_COUNT,
        f"got {shortlist['proven_count']}",
    )
    check(
        "verified qualifiers",
        shortlist["verified_qualifying"] == EXPECTED_VERIFIED_QUALIFYING,
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


def check_provenance(tables):
    """The check must pass real prose and catch the fabrication we actually saw."""
    import tools

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
        _normalise("11.7") in payload_numbers(segment),
        "display strings should supply the readable form, not an expansion rule",
    )
    check(
        "date digits in payload strings are allowed",
        provenance_check("Covers 22 Sep to 21 Dec 2020.", facts)[0],
        "dates come from the payload's own strings",
    )


def check_docs_are_current(tables):
    """The docs are generated, so the files on disk must match what code makes.

    A README is where a stale number survives longest: nothing renders it, so
    nothing catches it. Regenerating and comparing is the only way the figures
    in prose stay tied to the data.
    """
    from pathlib import Path

    import write_docs

    for relative_path, builder in write_docs.DOCUMENTS:
        path = Path(__file__).parent / relative_path
        check(
            f"{relative_path} exists",
            path.exists(),
            "run python write_docs.py",
        )
        check(
            f"{relative_path} matches what write_docs.py generates",
            path.read_text() == builder(tables),
            "stale; run python write_docs.py",
        )

    dataflow = (Path(__file__).parent / "docs" / "dataflow.md").read_text()
    check(
        "the data flow sketch says pure Python, not pandas",
        "pandas" not in dataflow,
        "the compute step is stdlib only",
    )
    check(
        "the data flow sketch draws the five steps as a mermaid chart",
        "```mermaid" in dataflow and dataflow.count("VERIFY") >= 2,
        "the diagram is the point of this file; both verify branches must be drawn",
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


def check_tool_payloads(tables):
    """Every tool returns the same envelope, and `n` is never silently missing.

    Sample size is the honesty mechanism: "9 creators" and "9 of 45" read very
    differently. If `n` can arrive null, the narration layer can drop it.
    """
    import tools

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
        payloads["metric_by_segment"]["ratio_text"] == "7.6x",
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


NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalise(token):
    """'1,000' and '1000' are the same number. '9.10' and '9.1' are too."""
    token = token.replace(",", "")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token or "0"


def _forms_of(value):
    """The ways a writer might reasonably render one payload number."""
    forms = {str(value), f"{value:,}"}
    if isinstance(value, float):
        forms |= {
            f"{value:.0f}",
            f"{value:.1f}",
            f"{value:.2f}",
            f"{value:,.0f}",
            f"{value:,.1f}",
        }
    return {_normalise(form) for form in forms}


def payload_numbers(payload):
    """Every number the payload actually contains, in every renderable form.

    Deliberately does NOT expand a rate into its percentage. Payloads ship a
    `_display` string for every rate, so the readable form is already present
    as text. Auto-expanding would widen the allowed set enough to let an
    invented figure through, which is the one thing this check exists to stop.
    """
    allowed = set()

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, bool):
            pass  # bools are ints in Python; they are not figures
        elif isinstance(node, (int, float)):
            allowed.update(_forms_of(node))
        elif isinstance(node, str):
            for token in NUMBER_PATTERN.findall(node):
                allowed.add(_normalise(token))

    walk(payload)
    return allowed


def provenance_check(narration, payload):
    """Return (ok, unbacked_tokens) for one narrated answer.

    The model is instructed never to invent a number. During live testing it
    did anyway, on 4 of 5 runs, with figures close enough to the truth to read
    as correct. An instruction is not a mechanism. This is the mechanism.
    """
    allowed = payload_numbers(payload)
    unbacked = [
        token
        for token in NUMBER_PATTERN.findall(narration)
        if _normalise(token) not in allowed
    ]
    return not unbacked, unbacked


def run_all():
    videos = prep.load_rows()
    tables = metrics.build_tables(videos)

    check_source_data(videos)
    check_percentiles(videos)
    check_scores(videos, tables)
    check_duration_table(tables)
    check_creator_table(tables)
    check_funnel_and_shortlist(tables)
    check_no_means_on_display(tables)
    check_segment_ratios(tables)
    check_tool_payloads(tables)
    check_provenance(tables)
    check_docs_are_current(tables)

    return tables


if __name__ == "__main__":
    try:
        run_all()
    except AssertionError as failure:
        print(f"CHECK FAILED: {failure}")
        print(f"({len(passed_checks)} checks passed before the failure)")
        sys.exit(1)

    for label, count in Counter(passed_checks).items():
        suffix = f" (x{count})" if count > 1 else ""
        print(f"  ok  {label}{suffix}")
    print(f"\nALL CHECKS PASSED ({len(passed_checks)} asserts)")
