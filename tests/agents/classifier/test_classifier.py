import json
import unittest

from app.agents.classifier import ClassificationResult, classify_document


class ClassifierTests(unittest.TestCase):
    def assert_type(self, text: str, expected: str) -> ClassificationResult:
        result = classify_document(text)
        self.assertEqual(expected, result.document_type, result)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        self.assertTrue(result.reason)
        json.dumps(result.to_dict(), ensure_ascii=False)
        return result

    def test_credit_application(self) -> None:
        self.assert_type(
            """CERERE DE CREDIT. Solicit acordarea unui împrumut. Suma solicitată:
            1.500.000 RON. Destinația creditului: capital de lucru. Perioada de
            creditare: 36 luni. Garanții propuse de solicitant.""",
            "application",
        )

    def test_balance_sheet(self) -> None:
        self.assert_type(
            """SITUAȚII FINANCIARE ANUALE. BILANȚ. Active imobilizate 900.000 lei,
            active circulante 2.100.000 lei, datorii 700.000 lei, capitaluri
            proprii 2.300.000 lei. Cont de profit și pierdere.""",
            "bilant",
        )

    def test_onrc_certificate(self) -> None:
        self.assert_type(
            """OFICIUL NAȚIONAL AL REGISTRULUI COMERȚULUI. CERTIFICAT CONSTATATOR.
            Număr de ordine în registrul comerțului J00/100/2020. Sediu social,
            activitate principală, cod CAEN și administratori.""",
            "onrc",
        )

    def test_tax_certificate(self) -> None:
        self.assert_type(
            """AGENȚIA NAȚIONALĂ DE ADMINISTRARE FISCALĂ. CERTIFICAT DE ATESTARE
            FISCALĂ privind obligațiile fiscale restante la bugetul general
            consolidat. Document eliberat la cererea contribuabilului.""",
            "caf",
        )

    def test_unrelated_document(self) -> None:
        self.assert_type(
            "Proces-verbal de recepție pentru livrarea a zece calculatoare și monitoare.",
            "unknown",
        )

    def test_empty_input(self) -> None:
        self.assert_type(" \n\t ", "unknown")

    def test_ambiguous_document(self) -> None:
        self.assert_type(
            """Cerere de credit. Suma solicitată și destinația creditului.
            Certificat de atestare fiscală. Obligații fiscale restante și
            bugetul general consolidat.""",
            "unknown",
        )

    def test_without_diacritics(self) -> None:
        self.assert_type(
            "CERTIFICAT CONSTATATOR emis de OFICIUL REGISTRULUI COMERTULUI. Sediu social, cod CAEN, administratori.",
            "onrc",
        )

    def test_inconsistent_case_and_spacing(self) -> None:
        self.assert_type(
            "sItUaȚiI   FiNaNcIaRe   AnUaLe\n\nCIFRA   DE AFACERI NETĂ 500000\nACTIVE CIRCULANTE 100000",
            "bilant",
        )

    def test_anaf_mention_alone_is_not_caf(self) -> None:
        self.assert_type(
            "Adresă către ANAF. Vă transmitem solicitarea de actualizare a adresei de corespondență a societății.",
            "unknown",
        )

    def test_demo_02_style_balance_sheet_uses_document_evidence(self) -> None:
        self.assert_type(
            """AGRO NORD TRANS SRL — SITUAȚII FINANCIARE ANUALE 2024.
            BILANȚ: active imobilizate 3.200.000 RON; active circulante
            5.800.000 RON; capitaluri proprii 4.100.000 RON. CONT DE PROFIT
            ȘI PIERDERE: cifra de afaceri netă 12.400.000 RON; profit net
            920.000 RON.""",
            "bilant",
        )


if __name__ == "__main__":
    unittest.main()
