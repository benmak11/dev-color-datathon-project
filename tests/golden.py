"""Ten questions with hand-checked answers, end to end through the answer path.

This tests routing and provenance, not wording. The model phrases things
differently every run, so asserting on prose would fail for the wrong reason.
What must hold is that the question reached the right prepared table, at the
right sample size, and that every figure in the answer traces back to it.

The first four questions are the chips on the question screen. The demo script
and the regression test are the same list, which is why neither gets skipped
when the clock runs out.

Offline mode needs no API key and runs as part of `python -m tests`. Run
`python -m tests.golden anthropic` to exercise the live model as well, or
`python -m tests.golden` for both.
"""

import sys

from core import llm
from core.provenance import provenance_check

Case = tuple  # (question, expected_tool, expected_n, fact_that_must_be_present)

GOLDEN_SET = [
    # The four chips.
    ("which creators get the most engagement?", "top_creators", 45, "reus.fx"),
    ("does video length matter?", "metric_by_segment", 1000, "30-60s"),
    ("are verified creators worth more?", "metric_by_segment", 1000, "7.6x"),
    ("tell me about papaswolio", "creator_profile", 4, "Proven"),
    # The rest.
    ("who should I reach out to first?", "top_creators", 45, "reus.fx"),
    # Must NOT refuse: content format is answerable, content topic is not.
    ("what kind of content should they make?", "metric_by_segment", 1000, "30-60s"),
    ("does original sound help?", "metric_by_segment", 1000, "Original sound"),
    # Must refuse. The reason is written by the model, so accept any wording
    # that names the right gap rather than one exact phrase.
    ("how many followers does reus.fx have?", "cannot_answer", None, ("follower",)),
    (
        "who will blow up next year?",
        "cannot_answer",
        None,
        ("predict", "future", "grow"),
    ),
    # Must answer with the median and say so.
    ("what is the average views?", "dataset_facts", 1000, "median, not an average"),
]


def check_case(question, expected_tool, expected_n, fact, mode):
    """Return (passed, failures, result) for one question in one mode."""
    result = llm.answer(question, mode=mode)
    payload = result.payload
    verified, unbacked = provenance_check(result.prose, payload)
    failures = []

    if result.call.name != expected_tool:
        failures.append(f"routed to {result.call.name}, expected {expected_tool}")
    if payload["n"] != expected_n:
        failures.append(f"sample size {payload['n']}, expected {expected_n}")
    if not verified:
        failures.append(f"unverifiable figures {unbacked}")
    wanted = (fact,) if isinstance(fact, str) else fact
    if not any(option.lower() in str(payload).lower() for option in wanted):
        failures.append(f"none of {wanted} in the data behind the answer")
    if mode != "offline" and result.mode != mode:
        failures.append(f"fell back to {result.mode}")

    return not failures, failures, result


def run(mode, verbose=True):
    """Run the whole set in one mode. Returns True when all ten pass."""
    if verbose:
        print(f"\n{mode.upper()} MODE")
        print("-" * 78)
    passed = 0

    for index, (question, tool, sample, fact) in enumerate(GOLDEN_SET, start=1):
        ok, failures, result = check_case(question, tool, sample, fact, mode)
        passed += ok
        if verbose:
            status = "PASS" if ok else "FAIL"
            print(f"{status}  {index:>2}. {question}")
            print(f"          {result.call.name}, n={result.payload['n']}")
            for failure in failures:
                print(f"          -> {failure}")

    if verbose:
        print("-" * 78)
        print(f"{passed}/{len(GOLDEN_SET)} passed in {mode} mode")
    return passed == len(GOLDEN_SET)


def check_all():
    """The offline path, for the main suite. No API key, no network."""
    from tests.runner import check

    check(
        "all ten golden questions pass offline",
        run("offline", verbose=False),
        "run python -m tests.golden offline to see which",
    )


if __name__ == "__main__":
    requested = sys.argv[1] if len(sys.argv) > 1 else None
    modes = [requested] if requested else ["offline", "anthropic"]

    results = {mode: run(mode) for mode in modes}

    print()
    if all(results.values()):
        print(f"ALL MODES PASSED ({', '.join(results)})")
    else:
        failed = [mode for mode, ok in results.items() if not ok]
        print(f"FAILED IN: {', '.join(failed)}")
        sys.exit(1)
