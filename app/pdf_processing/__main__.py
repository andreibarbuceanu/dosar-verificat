from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .demo_samples import generate_demo_02_pdfs
from .extractor import process_multiple_pdfs, process_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dosar Verificat - Componenta 1: PDF Processing (Extragere text pe pagini + R14/R15)"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Căi către fișiere PDF sau directoare cu PDF-uri de procesat.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generează și procesează cele 4 PDF-uri DEMO-02 (AGRO NORD TRANS SRL).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Salvează rezultatul JSON în fișierul specificat.",
    )
    args = parser.parse_args()

    pdf_files: list[Path] = []
    if args.demo or not args.paths:
        tmp_dir = Path(tempfile.gettempdir()) / "dosar_verificat_demo_02"
        created = generate_demo_02_pdfs(tmp_dir)
        pdf_files.extend(created.values())
    else:
        for p_str in args.paths:
            p = Path(p_str)
            if p.is_dir():
                pdf_files.extend(sorted(p.glob("*.pdf")))
            else:
                pdf_files.append(p)

    results = (
        process_pdf(pdf_files[0])
        if len(pdf_files) == 1
        else process_multiple_pdfs(pdf_files)
    )

    json_str = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
    else:
        sys.stdout.buffer.write((json_str + "\n").encode("utf-8"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

