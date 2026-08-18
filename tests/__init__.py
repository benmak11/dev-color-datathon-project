"""The test suite. Run it with `python -m tests`.

Plain assertions, no pytest. One command, an obvious exit code, and no
framework to configure. Every module here exposes functions that take the
already-built `videos` and `tables` so the data is loaded once for the whole
run rather than once per module.

Each module owns one concern:

    expectations   the hardcoded numbers every other module checks against
    runner         the `check` helper and the reporting
    source_data    the export itself: row counts, dates, uniqueness
    percentiles    the ranking, including a full recompute of every column
    aggregates     scores, duration buckets, creator table, funnel, ratios
    tool_payloads  the envelope every tool must return
    provenance     the guard that catches an invented figure
    documentation  the generated docs still match the data
    golden         ten questions end to end through the answer path
"""
