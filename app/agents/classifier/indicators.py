"""Weighted, document-specific terminology used by the classifier."""

from typing import Dict, Tuple


WeightedIndicator = Tuple[str, float]


INDICATORS: Dict[str, Tuple[WeightedIndicator, ...]] = {
    "application": (
        ("cerere de credit", 5.0),
        ("solicit acordarea", 3.5),
        ("suma solicitata", 3.0),
        ("valoarea creditului", 2.5),
        ("destinatia creditului", 2.5),
        ("perioada de creditare", 2.5),
        ("rambursare", 1.5),
        ("garantii propuse", 2.0),
        ("semnatura solicitantului", 2.0),
    ),
    "bilant": (
        ("bilant", 4.0),
        ("situatii financiare anuale", 5.0),
        ("situatia activelor datoriilor si capitalurilor proprii", 5.0),
        ("cont de profit si pierdere", 4.5),
        ("active imobilizate", 2.5),
        ("active circulante", 2.5),
        ("capitaluri proprii", 2.5),
        ("cifra de afaceri neta", 3.0),
        ("profit net", 2.0),
        ("datorii", 1.0),
        ("formular 10", 2.5),
        ("formular 20", 2.5),
    ),
    "onrc": (
        ("certificat constatator", 5.0),
        ("oficiul national al registrului comertului", 5.0),
        ("oficiul registrului comertului", 4.0),
        ("registrul comertului", 2.0),
        ("numar de ordine in registrul comertului", 3.5),
        ("sediu social", 2.0),
        ("activitate principala", 2.0),
        ("cod caen", 2.0),
        ("administratori", 1.5),
        ("starea firmei", 2.0),
    ),
    "caf": (
        ("certificat de atestare fiscala", 6.0),
        ("atestare fiscala", 3.0),
        ("obligatii fiscale", 2.5),
        ("obligatii fiscale restante", 3.5),
        ("bugetul general consolidat", 3.0),
        ("organ fiscal", 2.0),
        ("agentia nationala de administrare fiscala", 2.0),
        ("administratia judeteana a finantelor publice", 2.5),
        ("valabilitate", 1.0),
        ("eliberat la cererea", 1.5),
    ),
}
