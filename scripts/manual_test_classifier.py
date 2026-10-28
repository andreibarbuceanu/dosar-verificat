#!/usr/bin/env python3
"""Manual smoke tests for the public document-classifier API.

Run from the repository root with:
    python3 scripts/manual_test_classifier.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


# Allow direct execution without installing the repository as a package.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.agents.classifier import DocumentType, classify_document  # noqa: E402


@dataclass(frozen=True)
class ManualCase:
    name: str
    expected: DocumentType
    text: str


CASES = (
    ManualCase(
        name="Credit application",
        expected="application",
        text="""
            CERERE DE CREDIT
            Subsemnata societate solicit acordarea unei facilități de credit.
            Suma solicitată este 850.000 RON, cu destinația creditului pentru
            capital de lucru și o perioadă de creditare de 24 luni.
            Garanții propuse: ipotecă mobiliară. Semnătura solicitantului.
        """,
    ),
    ManualCase(
        name="Balance sheet",
        expected="bilant",
        text="""
            SITUAȚII FINANCIARE ANUALE — BILANȚ
            Active imobilizate: 1.100.000 lei
            Active circulante: 2.450.000 lei
            Datorii: 900.000 lei; Capitaluri proprii: 2.650.000 lei
            CONT DE PROFIT ȘI PIERDERE — profit net: 310.000 lei
        """,
    ),
    ManualCase(
        name="ONRC certificate",
        expected="onrc",
        text="""
            OFICIUL NAȚIONAL AL REGISTRULUI COMERȚULUI
            CERTIFICAT CONSTATATOR
            Număr de ordine în registrul comerțului: J40/1234/2021.
            Sediu social: București. Activitate principală: transporturi.
            Cod CAEN 4941. Administratori: Ionescu Maria.
        """,
    ),
    ManualCase(
        name="Tax certificate (CAF)",
        expected="caf",
        text="""
            AGENȚIA NAȚIONALĂ DE ADMINISTRARE FISCALĂ
            CERTIFICAT DE ATESTARE FISCALĂ
            La data emiterii, contribuabilul nu figurează cu obligații fiscale
            restante către bugetul general consolidat. Eliberat la cererea sa.
        """,
    ),
    ManualCase(
        name="Completely unrelated document",
        expected="unknown",
        text="""
            PROCES-VERBAL DE RECEPȚIE
            Au fost recepționate douăzeci de scaune și cinci birouri, conform
            contractului de furnizare. Produsele nu prezintă defecte vizibile.
        """,
    ),
    ManualCase(
        name="Empty document",
        expected="unknown",
        text="  \n\t  ",
    ),
    ManualCase(
        name="Ambiguous document",
        expected="unknown",
        text="""
            CERERE DE CREDIT. Suma solicitată și destinația creditului.
            CERTIFICAT DE ATESTARE FISCALĂ privind obligațiile fiscale restante
            către bugetul general consolidat.
        """,
    ),
    ManualCase(
        name="Text without Romanian diacritics",
        expected="onrc",
        text="""
            OFICIUL REGISTRULUI COMERTULUI — CERTIFICAT CONSTATATOR
            Numar de ordine in registrul comertului J12/999/2022.
            Sediu social, activitate principala, cod CAEN si administratori.
        """,
    ),
    ManualCase(
        name="Irregular whitespace",
        expected="bilant",
        text="SITUAȚII     FINANCIARE\n\nANUALE\t\tBILANȚ\nACTIVE    CIRCULANTE  780000\nCAPITALURI     PROPRII  510000",
    ),
    ManualCase(
        name="ANAF mention that is not a CAF",
        expected="unknown",
        text="""
            Către ANAF,
            Vă rugăm să actualizați adresa de corespondență electronică pentru
            societatea noastră. Atașăm împuternicirea reprezentantului legal.
        """,
    ),
    ManualCase(
        name="DEMO-02-style balance sheet",
        expected="bilant",
        text="""
            AGRO NORD TRANS SRL
            SITUAȚII FINANCIARE ANUALE 2024 — BILANȚ
            Active imobilizate: 3.200.000 RON
            Active circulante: 5.800.000 RON
            Capitaluri proprii: 4.100.000 RON
            CONT DE PROFIT ȘI PIERDERE
            Cifra de afaceri netă: 12.400.000 RON
            Profit net: 920.000 RON
        """,
    ),
)


def main() -> int:
    passed = 0

    for index, case in enumerate(CASES, start=1):
        result = classify_document(case.text)
        succeeded = result.document_type == case.expected
        passed += int(succeeded)

        print(f"[{index:02d}] {case.name}")
        print(f"     Expected:   {case.expected}")
        print(f"     Actual:     {result.document_type}")
        print(f"     Confidence: {result.confidence:.2f}")
        print(f"     Reason:     {result.reason}")
        print(f"     Result:     {'PASS' if succeeded else 'FAIL'}")
        print()

    failed = len(CASES) - passed
    print(f"Summary: {passed} passed, {failed} failed, {len(CASES)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
