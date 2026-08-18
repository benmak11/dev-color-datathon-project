"""The five tools the Q&A layer is allowed to call, over the precomputed tables.

Every tool returns the same envelope, and every number in it was computed by
`metrics`. The model chooses a tool and narrates the result. It never computes,
so anything it would otherwise have to divide is precomputed here and shipped
as display text.

The envelope always carries `n`, the sample the rows were drawn from. "9
creators" and "9 of 45" read very differently to a non-technical reader, and
the difference has to survive the trip to the model.
"""

import difflib

import metrics

SUGGESTION_LIMIT = 3
SUGGESTION_CUTOFF = 0.6
MAX_ROWS = 25
THIN_EVIDENCE_VIDEOS = 3

SEGMENT_GROUP_LABELS = {
    "verified": {True: "Verified", False: "Not verified"},
    "music_is_original": {True: "Original sound", False: "Licensed sound"},
}

METRIC_LABELS = {
    "median_views": "median views",
    "median_engagement_rate": "median engagement rate",
    "median_score": "median engagement score",
    "n_videos": "number of videos",
}

TABLES = metrics.build_tables()


def _scope_note():
    """Rides on every payload. Generated, because Rule 2 forbids typing it."""
    facts = TABLES["dataset_facts"]
    return (
        f"Covers {facts['rows']:,} trending videos from {facts['date_min']} to "
        f"{facts['date_max']}. Every video in this batch already trended."
    )


SCOPE_NOTE = _scope_note()


def _thin_evidence_note(rows):
    """Flag two-video creators in the rows, so the model cannot quietly omit it."""
    thin = [row for row in rows if row.get("n_videos", 0) < THIN_EVIDENCE_VIDEOS]
    if not thin:
        return None
    return (
        f"{len(thin)} of these {len(rows)} rest on 2 videos. Real signal, thin "
        "evidence."
    )


def _envelope(tool, filters, rows, n, unit, notes=None, **extra):
    payload = {
        "tool": tool,
        "filters": filters,
        "n": n,
        "unit": unit,
        "rows": rows,
        "notes": [note for note in (notes or []) if note] + [SCOPE_NOTE],
    }
    payload.update(extra)
    return payload


def as_percent(rate):
    return f"{rate * 100:.1f}%"


def as_count(value):
    return f"{int(value):,}"


def _display_metric(name, value):
    if name in ("median_engagement_rate", "median_like_rate"):
        return as_percent(value)
    if name == "median_views":
        return as_count(value)
    if name == "median_score":
        return f"{round(value * 100)} out of 100"
    return str(value)


def _creator_row(creator):
    """The shape a creator takes when it appears in a list of results.

    Rates ship twice: the raw value, and a reader-ready string. The narration
    layer may not convert anything, so without the second form it quotes
    "0.0914" at a non-technical reader. Both are in the payload, so quoting the
    readable one still passes the provenance check.
    """
    return {
        "handle": creator["handle"],
        "n_videos": creator["n_videos"],
        "median_views": int(creator["median_views"]),
        "median_views_display": as_count(creator["median_views"]),
        "median_engagement_rate": round(creator["median_engagement_rate"], 4),
        "median_engagement_rate_display": as_percent(
            round(creator["median_engagement_rate"], 4)
        ),
        "engagement_score": round(creator["median_score"] * 100),
        # The scale belongs in the payload. Without it, a narration that writes
        # "84 out of 100" is quoting a number nothing gave it.
        "engagement_score_display": f"{round(creator['median_score'] * 100)} out of 100",
        "verified": creator["verified"],
    }


def top_creators(
    sort_by="score",
    n=10,
    min_videos=2,
    min_median_views=50_000,
    verified_only=False,
    qualifying_only=True,
):
    """Rank creators who clear the given bars.

    `qualifying_only` applies the third gate, engagement above the batch median,
    so the default population is the same 45 creators the summary screen
    reports. Without it the tool answers from 74 and quietly contradicts the
    screen she just read.
    """
    sort_keys = {
        "score": "median_score",
        "median_views": "median_views",
        "median_engagement_rate": "median_engagement_rate",
        "n_videos": "n_videos",
    }
    sort_key = sort_keys.get(sort_by, "median_score")
    n = max(1, min(int(n), MAX_ROWS))
    score_floor = TABLES["shortlist"]["gates"]["score_above"]

    matched = [
        creator
        for creator in TABLES["creator_table"]
        if creator["n_videos"] >= min_videos
        and creator["median_views"] >= min_median_views
        and (creator["verified"] if verified_only else True)
        and (creator["median_score"] > score_floor if qualifying_only else True)
    ]
    matched.sort(key=lambda creator: creator[sort_key], reverse=True)
    rows = [_creator_row(creator) for creator in matched[:n]]

    population = (
        "creators clearing all three bars"
        if qualifying_only
        else "creators clearing the video and reach bars only"
    )
    return _envelope(
        tool="top_creators",
        filters={
            "sort_by": sort_by,
            "n": n,
            "min_videos": min_videos,
            "min_median_views": min_median_views,
            "verified_only": verified_only,
            "qualifying_only": qualifying_only,
        },
        rows=rows,
        n=len(matched),
        unit=population,
        notes=[_thin_evidence_note(rows)],
    )


def _tier_for(creator):
    """Proven, Emerging, or the specific bar this creator failed."""
    gates = TABLES["shortlist"]["gates"]
    if creator["n_videos"] < gates["min_videos"]:
        return "Did not qualify: only 1 video in this batch"
    if creator["median_views"] < gates["min_median_views"]:
        return (
            "Did not qualify: median views below "
            f"{gates['min_median_views']:,}"
        )
    if creator["median_score"] <= gates["score_above"]:
        return "Did not qualify: engagement below the batch middle"
    return "Proven" if creator["n_videos"] >= THIN_EVIDENCE_VIDEOS else "Emerging"


def creator_profile(handle):
    """One creator, ordered for the decision of whether to open a conversation."""
    handle = (handle or "").strip().lstrip("@").lower()
    by_handle = {c["handle"].lower(): c for c in TABLES["creator_table"]}
    creator = by_handle.get(handle)

    if creator is None:
        suggestions = difflib.get_close_matches(
            handle, list(by_handle), n=SUGGESTION_LIMIT, cutoff=SUGGESTION_CUTOFF
        )
        return _envelope(
            tool="creator_profile",
            filters={"handle": handle},
            rows=[],
            n=0,
            unit="creators",
            notes=["No creator with that handle appears in this batch."],
            error="not_found",
            suggestions=suggestions,
        )

    scores_span = (
        round(creator["score_min"] * 100),
        round(creator["score_max"] * 100),
    )
    row = {
        "handle": creator["handle"],
        "tier": _tier_for(creator),
        "n_videos": creator["n_videos"],
        "median_views": int(creator["median_views"]),
        "median_views_display": as_count(creator["median_views"]),
        "best_video_views": int(creator["best_video_views"]),
        "best_video_views_display": as_count(creator["best_video_views"]),
        "median_engagement_rate": round(creator["median_engagement_rate"], 4),
        "median_engagement_rate_display": as_percent(creator["median_engagement_rate"]),
        "engagement_score": round(creator["median_score"] * 100),
        "score_range": f"{scores_span[0]} to {scores_span[1]}",
        "verified": creator["verified"],
        "top_hashtag": creator["top_hashtag"],
    }

    consistency = (
        f"All {creator['n_videos']} videos scored between {scores_span[0]} and "
        f"{scores_span[1]} out of 100."
    )
    return _envelope(
        tool="creator_profile",
        filters={"handle": creator["handle"]},
        rows=[row],
        n=creator["n_videos"],
        unit="videos by this creator",
        notes=[consistency, _thin_evidence_note([row])],
    )


def metric_by_segment(metric="median_engagement_rate", dimension="duration_bucket"):
    """Compare one metric across the groups of one dimension."""
    if dimension not in TABLES["segment_tables"]:
        dimension = "duration_bucket"
    if metric not in METRIC_LABELS:
        metric = "median_engagement_rate"

    segment_rows = TABLES["segment_tables"][dimension]
    labels = SEGMENT_GROUP_LABELS.get(dimension)

    # Every row carries all four metrics, not just the requested one. Asked
    # "are verified creators worth more?", a views-only payload plus a note
    # mentioning engagement left a gap, and the model filled it with invented
    # figures on 4 of 5 runs. The numbers were plausible enough to pass a human
    # read. Leave no gap to fill.
    rows = []
    for segment in segment_rows:
        group = segment.get("bucket", segment.get("group"))
        row = {
            "group": labels[group] if labels else group,
            "n_videos": segment["n_videos"],
            "requested_metric": metric,
        }
        for name in METRIC_LABELS:
            if name not in segment:
                continue
            # Round FIRST, then format. Formatting the unrounded value while
            # exposing the rounded one made the same rate read 7.3% in the
            # table and 7.2% in the prose.
            value = segment[name]
            value = round(value, 4) if isinstance(value, float) else value
            row[name] = value
            row[f"{name}_display"] = _display_metric(name, value)
        rows.append(row)

    # Two-group dimensions carry the multiple as text, so the model never divides.
    ratio_text = None
    notes = []
    if labels and metric in segment_rows[0].get("ratios", {}):
        ratio_text = segment_rows[0]["ratios"][metric]["text"]
        notes.append(
            f"{rows[0]['group']} videos have {ratio_text} the "
            f"{METRIC_LABELS[metric]} of {rows[1]['group'].lower()} videos."
        )

    if dimension == "verified":
        views = segment_rows[0]["ratios"]["median_views"]["text"]
        score = segment_rows[0]["ratios"]["median_score"]["text"]
        notes.append(
            f"Verified videos take {views} the median views but score {score} on "
            "the blended engagement metric, which is lower. Verified buys scale. "
            "Unverified buys engagement per view."
        )

    return _envelope(
        tool="metric_by_segment",
        filters={"metric": metric, "dimension": dimension},
        rows=rows,
        n=sum(row["n_videos"] for row in rows),
        unit="videos",
        notes=notes,
        ratio_text=ratio_text,
    )


def dataset_facts():
    """What this dataset is, and the shape of the shortlist funnel."""
    facts = TABLES["dataset_facts"]
    shortlist = TABLES["shortlist"]
    row = {
        "videos": facts["rows"],
        "creators": facts["creators"],
        "date_min": facts["date_min"],
        "date_max": facts["date_max"],
        "total_views": facts["total_views"],
        "median_views": int(facts["median_views"]),
        "median_views_display": as_count(facts["median_views"]),
        "median_engagement_rate": round(facts["median_engagement_rate"], 4),
        "median_engagement_rate_display": as_percent(facts["median_engagement_rate"]),
        "creators_with_2plus_videos": shortlist["funnel"]["with_2plus"],
        "creators_clearing_reach_floor": shortlist["funnel"]["clearing_reach_floor"],
        "creators_qualifying": shortlist["funnel"]["qualifying"],
        "proven_count": shortlist["proven_count"],
        "verified_qualifying": shortlist["verified_qualifying"],
    }
    return _envelope(
        tool="dataset_facts",
        filters={},
        rows=[row],
        n=facts["rows"],
        unit="videos",
        notes=[
            # Someone will ask for an average. Views are skewed hard enough
            # (mean 1,029,213 against median 82,500) that answering with one
            # would mislead, so the payload says which it gave and why.
            "Every figure here is a median, not an average. Views are skewed "
            "enough that an average would describe no real video.",
            "There are no follower counts in this dataset. Reach is views only.",
            f"Of {facts['creators']:,} creators, "
            f"{shortlist['funnel']['qualifying']} clear all three bars and "
            f"{shortlist['proven_count']} of those have 3 or more videos.",
        ],
    )


def cannot_answer(reason):
    """The refusal path. A routing outcome, not an error."""
    return _envelope(
        tool="cannot_answer",
        filters={"reason": reason},
        rows=[],
        n=None,
        unit="none",
        notes=[reason],
    )


SCHEMAS = [
    {
        "name": "top_creators",
        "description": (
            "Rank creators in this batch of trending videos. Use for questions "
            "about who to approach, who performs best, who gets the most "
            "engagement or the most views, and for the shortlist itself. "
            "Defaults apply the three qualifying bars."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": [
                        "score",
                        "median_views",
                        "median_engagement_rate",
                        "n_videos",
                    ],
                    "description": (
                        "score is the blended engagement rank and is the default. "
                        "median_views is reach."
                    ),
                },
                "n": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS},
                "min_videos": {
                    "type": "integer",
                    "description": "Minimum videos in this batch. Default 2.",
                },
                "min_median_views": {
                    "type": "integer",
                    "description": "Reach floor. Default 50000.",
                },
                "verified_only": {"type": "boolean"},
                "qualifying_only": {
                    "type": "boolean",
                    "description": (
                        "Default true, which restricts to the creators clearing "
                        "all three bars. Set false only to look beyond the "
                        "shortlist."
                    ),
                },
            },
        },
    },
    {
        "name": "creator_profile",
        "description": (
            "Everything known about one named creator, including which tier they "
            "fall in and which bar they failed if they did not qualify. Use when "
            "the question names a handle."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string", "description": "The creator's handle."}
            },
            "required": ["handle"],
        },
    },
    {
        "name": "metric_by_segment",
        "description": (
            "Compare one metric across the groups of one dimension. Use for "
            "content questions about video length or sound, and for questions "
            "about whether verified creators perform differently. This is the "
            "tool for 'what should they make', since format is answerable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": list(METRIC_LABELS),
                },
                "dimension": {
                    "type": "string",
                    "enum": ["duration_bucket", "verified", "music_is_original"],
                    "description": (
                        "duration_bucket is video length. music_is_original is "
                        "original versus licensed sound."
                    ),
                },
            },
            "required": ["metric", "dimension"],
        },
    },
    {
        "name": "dataset_facts",
        "description": (
            "Size, date range and shortlist funnel of the dataset. Use for "
            "questions about how much data there is, what it covers, or how the "
            "shortlist was narrowed."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cannot_answer",
        "description": (
            "Use when the dataset cannot answer the question. It has no follower "
            "counts, no audience demographics, no fees or rate cards, no data "
            "after December 2020, and no content topic labels. It also cannot "
            "support causal or predictive claims about who will grow. Give the "
            "specific reason."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Plain-English reason, naming what is missing.",
                }
            },
            "required": ["reason"],
        },
    },
]

REGISTRY = {
    "top_creators": top_creators,
    "creator_profile": creator_profile,
    "metric_by_segment": metric_by_segment,
    "dataset_facts": dataset_facts,
    "cannot_answer": cannot_answer,
}


if __name__ == "__main__":
    import json

    for name in REGISTRY:
        print(f"  {name}")
    print()
    print(json.dumps(metric_by_segment("median_views", "verified"), indent=2))
