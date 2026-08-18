"""The docs are generated, so the files on disk must match what code makes.

A README is where a stale number survives longest: nothing renders it, so
nothing catches it. Regenerating and comparing is the only way the figures in
prose stay tied to the data.
"""

from core.paths import DOCS_DIR, PROJECT_ROOT
from scripts import write_docs
from tests.runner import check


def check_all(tables):
    for relative_path, builder in write_docs.DOCUMENTS:
        path = PROJECT_ROOT / relative_path
        check(
            f"{relative_path} exists",
            path.exists(),
            "run python -m scripts.write_docs",
        )
        check(
            f"{relative_path} matches what write_docs generates",
            path.read_text() == builder(tables),
            "stale; run python -m scripts.write_docs",
        )

    dataflow = (DOCS_DIR / "dataflow.md").read_text()
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

    readme = (PROJECT_ROOT / "README.md").read_text()
    check(
        "the README shows the directory layout",
        "core/" in readme and "tests/" in readme,
        "the file map is how a reader finds their way around",
    )
