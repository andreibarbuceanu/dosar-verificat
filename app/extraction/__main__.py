"""python -m app.extraction <file.pdf> --type bilant [--doc-id ID] [--print-prompt]

Prints the ExtractionResult as JSON. The model comes from app.llm (LLM_BACKEND=cli|api|replay).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fields import DOC_TYPES
from .pdf import extract_pages, extract_pdf
from .prompt import build_prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.extraction")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--type", dest="doc_type", required=True, choices=DOC_TYPES)
    parser.add_argument("--doc-id", default=None, help="defaults to the file name without extension")
    parser.add_argument("--print-prompt", action="store_true",
                        help="print the prompt instead of calling the model")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.print_prompt:
        print(build_prompt(args.doc_type, extract_pages(args.pdf)))
        return 0
    try:
        result = extract_pdf(args.pdf, args.doc_id or args.pdf.stem, args.doc_type)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
