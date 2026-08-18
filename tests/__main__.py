"""Run the whole suite: `python -m tests`.

The data is loaded once here and handed to every module, so a full run is one
pass over the export rather than one per concern.
"""

import sys

from core import metrics, prep
from tests import (
    aggregates,
    documentation,
    golden,
    percentiles,
    provenance,
    source_data,
    tool_payloads,
)
from tests.runner import report_failure, report_success


def run_all():
    videos = prep.load_rows()
    tables = metrics.build_tables(videos)

    source_data.check_all(videos)
    percentiles.check_all(videos)
    aggregates.check_all(videos, tables)
    tool_payloads.check_all(tables)
    provenance.check_all(tables)
    documentation.check_all(tables)
    golden.check_all()

    return tables


if __name__ == "__main__":
    try:
        run_all()
    except AssertionError as failure:
        report_failure(failure)
        sys.exit(1)

    report_success()
