"""Route a plain-English question to one tool, then narrate what came back.

This module holds the offline path: keyword routing and templated narration.
It exists first and on purpose. No API key is needed to demo the flow, and
whoever reviews this repo will not have one. The Anthropic path arrives next
and falls back to these same functions on any failure.

Both paths call the same tools and return the same payloads, so the answer a
reader sees is backed by identical numbers either way. Only the wording and
the routing differ.
"""

import os
import re
from collections import namedtuple
from pathlib import Path

import tools

# The key lives in .env, not the shell, so nothing else on the machine inherits
# it. os.environ.setdefault means a real exported variable always wins.
_ENV_FILE = Path(__file__).parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        if _line.strip() and not _line.startswith("#") and "=" in _line:
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip())

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

# Thinking stays on. Disabling it on this model has a documented failure mode
# where a tool call arrives as plain text instead of a tool_use block: the turn
# succeeds, the tool never runs, and nothing raises. For a router that is the
# worst possible failure. Low effort gets the latency saving safely instead.
ROUTING_EFFORT = "low"
NARRATION_EFFORT = "low"
ROUTING_MAX_TOKENS = 2048
NARRATION_MAX_TOKENS = 1024

ROUTER_SYSTEM = """You route questions about a batch of trending TikTok videos to \
exactly one tool. You never answer from your own knowledge.

The dataset is 1,000 trending videos from 802 creators, 22 Sep to 21 Dec 2020. \
It has views, likes, comments, shares, verified status, video duration, whether \
the sound is original, and hashtags. It has NO follower counts, no audience \
demographics, no fees or rates, no data after December 2020, and no content \
topic labels.

Draw this distinction carefully:
- Content FORMAT is answerable. "What kind of content should they make?" and \
"how long should videos be?" are about duration and sound, so use \
metric_by_segment. Do not refuse these.
- Content TOPIC is not answerable. "What subjects do they post about?" has no \
answer here, because the hashtags are generic discovery tags. Use cannot_answer.

Use cannot_answer for follower counts, audience demographics, fees or revenue, \
anything after December 2020, predictions about future performance, and \
questions about why something happened."""

NARRATOR_SYSTEM = """You explain one prepared result to a Head of Creator \
Partnerships who is not technical.

Answer the question. The result you are given was chosen because it answers it, \
so lead with the answer rather than with what the data cannot do. In \
particular, questions about what creators should make ARE answered by video \
length and sound: that is what "content" means here, so answer them directly \
instead of saying the data does not cover content. A question about who to \
approach IS answered by the ranking you are given; name the creators.

Rules you must follow:
- Use only the JSON you are given. Every number you write must already appear \
in that JSON. Do not add, average, divide, round, or convert anything.
- When a field ends in "_display", quote that version rather than the raw \
number. "9.1%" reads; "0.0914" does not.
- State the sample size once.
- Under 70 words. No headers, no bullet lists, no preamble.
- Describe what the batch shows. Do not claim one thing caused another, and do \
not predict.
- One short caveat at most, only if it changes what she would do. The scope of \
the data is already on screen, so do not restate it.
- If the JSON genuinely does not answer the question, say so in one sentence \
and stop."""

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


_last_fallback_reason = None


def record_fallback(failure):
    """Remember why the model path failed, so the screen can say so."""
    global _last_fallback_reason
    _last_fallback_reason = f"{type(failure).__name__}: {failure}"


def last_fallback_reason():
    return _last_fallback_reason


def _client():
    import anthropic

    return anthropic.Anthropic()


def route(question):
    """Ask the model to pick one tool. Refusal to answer is itself a tool."""
    response = _client().messages.create(
        model=MODEL,
        max_tokens=ROUTING_MAX_TOKENS,
        output_config={"effort": ROUTING_EFFORT},
        system=[
            {
                "type": "text",
                "text": ROUTER_SYSTEM,
                # System and tools are byte-identical on every question, so the
                # prefix caches and only the question is billed at full price.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=tools.SCHEMAS,
        # Forcing a tool call is what makes refusal a routing outcome rather
        # than a keyword filter bolted on in front of the model.
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": question}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined to route this question")

    for block in response.content:
        if block.type == "tool_use":
            return ToolCall(block.name, dict(block.input))

    raise RuntimeError("no tool call in the routing response")


def narrate(question, payload):
    """Explain the computed payload. The model sees only what code produced."""
    import json

    response = _client().messages.create(
        model=MODEL,
        max_tokens=NARRATION_MAX_TOKENS,
        output_config={"effort": NARRATION_EFFORT},
        system=[
            {
                "type": "text",
                "text": NARRATOR_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Prepared result:\n{json.dumps(payload, indent=2)}"
                ),
            }
        ],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined to narrate this result")

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise RuntimeError("empty narration")
    return text.strip()


def answer(question):
    """Route, compute, narrate. The one entry point the screen calls.

    Any failure at all falls through to the offline path: no key, a bad model
    id, a timeout, a rate limit, a refusal. The reader still gets an answer
    backed by the same numbers, and the banner says which path produced it.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            call = route(question)
            payload = tools.REGISTRY[call.name](**call.arguments)
            return Answer(narrate(question, payload), payload, call, "anthropic")
        except Exception as failure:
            # Record why, never swallow it. A fallback that hides its reason
            # looks identical to having no key at all, and the first time this
            # fired the cause was a billing state no amount of code would fix.
            record_fallback(failure)

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
