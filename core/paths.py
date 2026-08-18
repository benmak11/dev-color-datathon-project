"""Where things live on disk, resolved once.

Every path is derived from the project root rather than from the importing
module's own location. Before this existed, `prep.py` and `llm.py` each built
paths from `Path(__file__).parent`, which silently pointed at the wrong
directory the moment either file moved into a package.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = PROJECT_ROOT / "data" / "2026datathon_interview_data.csv"
ENV_FILE = PROJECT_ROOT / ".env"
DOCS_DIR = PROJECT_ROOT / "docs"
