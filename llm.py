"""Route a plain-English question to one tool, then narrate what came back.

This module holds the offline path: keyword routing and templated narration.
It exists first and on purpose. No API key is needed to demo the flow, and
whoever reviews this repo will not have one. The Anthropic path arrives next
and falls back to these same functions on any failure.

Both paths call the same tools and return the same payloads, so the answer a
reader sees is backed by identical numbers either way. Only the wording and
the routing differ.
"""

import re
from collections import namedtuple

import tools

ToolCall = namedtuple("ToolCall", "name arguments")
Answer = namedtuple("Answer", "prose payload call mode")

MAX_NAMED_CREATORS = 3
MAX_APPENDED_NOTES = 2

KNOWN_HANDLES = {c["handle"].lower() for c in tools.TABLES["creator_table"]}
HANDLE_TOKEN = re.compile(r"[a-z0-9._]{4,}")

# Refusals are matched FIRST. "how many followers does reus.fx have?" contains a
# real handle, so any rule that looks for handles before checking scope will
# answer a question the dataset cannot answer.
REFUSAL_RULES = [
    (r"follower|subscriber", "this dataset has no follower or subscriber counts"),
    (r"demographic|audience age|gender|country|location",
     "this dataset has no audience demographics"),
    (r"rate card|fee|price|cost|revenue|earn|paid|salary|budget",
     "this dataset has no fees, rates or revenue"),
    (r"20(2[1-9]|[3-9][0-9])|next year|today|currently|right now|latest",
     "this dataset stops in December 2020"),
    (r"will (they|he|she|it|this)|going to|predict|forecast|blow up|grow into",
     "this dataset cannot predict future performance"),
    (r"\bwhy\b", "this dataset shows what happened, not why"),
    (r"topic|theme|niche|category|what are they (posting|making) about",
     "this dataset has no content topic labels, only generic discovery hashtags"),
]

# Ordered. First match wins.
ROUTING_RULES = [
    (r"most engagement|best engagement|highest engagement|most engaging",
     "top_creators", {"sort_by": "median_engagement_rate"}),
    (r"most views|biggest|largest reach|most reach",
     "top_creators", {"sort_by": "median_views"}),
    (r"verified",
     "metric_by_segment", {"metric": "median_views", "dimension": "verified"}),
    (r"long|short|second|duration|how long|length",
     "metric_by_segment",
     {"metric": "median_engagement_rate", "dimension": "duration_bucket"}),
    (r"original sound|music|audio|sound",
     "metric_by_segment",
     {"metric": "median_engagement_rate", "dimension": "music_is_original"}),
    (r"what.*(post|make|film|brief|create)|what kind of content|format",
     "metric_by_segment",
     {"metric": "median_engagement_rate", "dimension": "duration_bucket"}),
    (r"who|top|best|shortlist|focus|reach out|sign|approach|priorit",
     "top_creators", {}),
    (r"how many|how much|what is in|dataset|data set|overall|average|mean",
     "dataset_facts", {}),
]


def find_handle(question):
    """Return a handle named in the question, if the batch contains one."""
    for token in HANDLE_TOKEN.findall(question.lower()):
        if token in KNOWN_HANDLES:
            return token
    return None


def route_offline(question):
    """Pick one tool by keyword. Deterministic, and refusals are checked first."""
    text = (question or "").lower().strip()

    for pattern, reason in REFUSAL_RULES:
        if re.search(pattern, text):
            return ToolCall("cannot_answer", {"reason": reason})

    handle = find_handle(text)
    if handle:
        return ToolCall("creator_profile", {"handle": handle})

    for pattern, name, arguments in ROUTING_RULES:
        if re.search(pattern, text):
            return ToolCall(name, dict(arguments))

    return ToolCall("dataset_facts", {})


def _format_views(views):
    return f"{int(views):,}"


def _format_rate(rate):
    return f"{rate * 100:.1f}%"


def _leading_value(row, sort_by):
    """Show the figure the list was actually sorted by, not a different one."""
    if sort_by == "median_engagement_rate":
        return f"{_format_rate(row['median_engagement_rate'])} engagement rate"
    if sort_by == "median_views":
        return f"{_format_views(row['median_views'])} median views"
    if sort_by == "n_videos":
        return f"{row['n_videos']} videos"
    return f"{row['engagement_score']} out of 100"


def _narrate_top_creators(payload):
    rows = payload["rows"]
    if not rows:
        return "No creators in this batch match those filters."

    sort_by = payload["filters"]["sort_by"]
    named = ", ".join(
        f"{row['handle']} ({_leading_value(row, sort_by)}, {row['n_videos']} videos)"
        for row in rows[:MAX_NAMED_CREATORS]
    )
    sorted_by = sort_by.replace("_", " ")
    return (
        f"{payload['n']} {payload['unit']} qualify. Sorted by {sorted_by}, the "
        f"strongest are {named}."
    )


def _narrate_metric_by_segment(payload):
    metric = payload["filters"]["metric"]
    rows = payload["rows"]
    parts = []
    for row in rows:
        value = row[metric]
        shown = (
            _format_rate(value)
            if metric == "median_engagement_rate"
            else _format_views(value) if metric == "median_views" else value
        )
        parts.append(f"{row['group']} {shown} (n={row['n_videos']})")
    label = tools.METRIC_LABELS[metric]
    return f"Across {payload['n']} videos, {label} by group: " + "; ".join(parts) + "."


def _narrate_creator_profile(payload):
    if payload.get("error") == "not_found":
        suggestions = payload.get("suggestions")
        if suggestions:
            return (
                "No creator by that handle is in this batch. Closest matches: "
                + ", ".join(suggestions)
                + "."
            )
        return "No creator by that handle is in this batch."

    row = payload["rows"][0]
    return (
        f"{row['handle']} is {row['tier']}. {row['n_videos']} videos in this batch, "
        f"{_format_views(row['median_views'])} median views, best video "
        f"{_format_views(row['best_video_views'])} views, engagement score "
        f"{row['engagement_score']} out of 100."
    )


def _narrate_dataset_facts(payload):
    row = payload["rows"][0]
    return (
        f"{row['videos']:,} trending videos from {row['creators']:,} creators, "
        f"{row['date_min']} to {row['date_max']}. Median views {_format_views(row['median_views'])}, "
        f"median engagement rate {_format_rate(row['median_engagement_rate'])}. "
        f"{row['creators_qualifying']} creators clear all three bars, and "
        f"{row['proven_count']} of those have 3 or more videos."
    )


def _narrate_cannot_answer(payload):
    return (
        f"I cannot answer that from this data, because "
        f"{payload['filters']['reason']}."
    )


NARRATORS = {
    "top_creators": _narrate_top_creators,
    "metric_by_segment": _narrate_metric_by_segment,
    "creator_profile": _narrate_creator_profile,
    "dataset_facts": _narrate_dataset_facts,
    "cannot_answer": _narrate_cannot_answer,
}


def narrate_offline(payload):
    """Fill one template per tool from payload fields only.

    Deterministic by construction, so every figure in the prose is already in
    the payload and the Phase 8 provenance check passes without tuning.
    """
    prose = NARRATORS[payload["tool"]](payload)
    # Append the first note that adds something. Skip the scope note, which is
    # on screen already, and skip any note the prose has just said. Matching on
    # substrings like "lower" is what made a refusal repeat itself, because
    # "follower" contains it.
    extra = [
        note
        for note in payload["notes"]
        if note != tools.SCOPE_NOTE and note not in prose
    ]
    # Two notes, not one. "Are verified creators worth more?" returns the 7.6x
    # views multiple first and the lower engagement score second. Keeping only
    # the first answers "yes" and silently drops the qualification.
    return " ".join([prose] + extra[:MAX_APPENDED_NOTES])


def answer(question):
    """Route, compute, narrate. The one entry point the screen calls."""
    call = route_offline(question)
    payload = tools.REGISTRY[call.name](**call.arguments)
    return Answer(narrate_offline(payload), payload, call, "offline")


if __name__ == "__main__":
    demo_questions = [
        "which creators get the most engagement?",
        "does video length matter?",
        "are verified creators worth more?",
        "tell me about papaswolio",
        "who should I reach out to first?",
        "what kind of content should they make?",
        "does original sound help?",
        "how many followers does reus.fx have?",
        "who will blow up next year?",
        "what's the average views?",
    ]
    for question in demo_questions:
        result = answer(question)
        print(f"Q: {question}")
        print(f"   -> {result.call.name}{result.call.arguments or ''}")
        print(f"   {result.prose}")
        print()
