#!/usr/bin/env python3
"""Run the integrated Sprint 1 backend pipeline on the DEMO-02 PDFs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    os.environ.setdefault("LLM_BACKEND", "replay")
    pdfs = sorted((ROOT / "pdfs" / "DEMO-02").glob("*.pdf"))
    if not pdfs:
        print("No DEMO-02 PDFs found.", file=sys.stderr)
        return 1

    result = run_pipeline(
        "DEMO-02",
        [(path.stem, path) for path in pdfs],
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 1 if any(document.error for document in result.documents) else 0


if __name__ == "__main__":
    raise SystemExit(main())
