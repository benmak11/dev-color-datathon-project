"""The `check` helper and the reporting around it.

`check` is a labelled assert. The label is what turns a failure into a
sentence someone can act on, and it is what lets the run print what it
covered rather than only that it finished.
"""

from collections import Counter

passed_checks = []


def check(label, condition, detail=""):
    """Record a passing check, or fail loudly with the label and what went wrong."""
    assert condition, f"{label}: {detail}"
    passed_checks.append(label)


def reset():
    passed_checks.clear()


def report_success():
    for label, count in Counter(passed_checks).items():
        suffix = f" (x{count})" if count > 1 else ""
        print(f"  ok  {label}{suffix}")
    print(f"\nALL CHECKS PASSED ({len(passed_checks)} asserts)")


def report_failure(failure):
    print(f"CHECK FAILED: {failure}")
    print(f"({len(passed_checks)} checks passed before the failure)")
