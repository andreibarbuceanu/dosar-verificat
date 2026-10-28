from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PromptInjectionFlag:
    """Semnalare pentru Regula R15 (instrucțiuni ascunse / prompt injection în PDF)."""

    page: int
    reason: str  # "hidden_white_text" | "tiny_hidden_text" | "instruction_pattern"
    snippet: str
    rule_id: str = "R15"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]


@dataclass
class PageExtract:
    """Rezultatul extragerii textului de pe o singură pagină PDF (indexat de la 1).

    Funcționează atât ca obiect (`p.text`, `p.readable`, `p.page`) cât și ca dict (`p["text"]`, `p["readable"]`).
    """

    page: int
    text: str
    readable: bool
    char_count: int = 0
    has_images: bool = False
    is_scanned_only: bool = False
    hidden_texts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def keys(self) -> Any:
        return self.to_dict().keys()

    def __contains__(self, key: object) -> bool:
        return key in self.to_dict()


# Alias conform docs/CONTRACT.md: `extract_pages(path) -> list[Page]`
Page = PageExtract


@dataclass
class ProcessedDocument:
    """Rezultatul complet al procesării unui document PDF.

    Respectă simultan:
    - Contractul Document din CONTRACT.md: {"id", "type", "file", "pages", "readable"}
    - Cerințele Sprint 1 pentru AI Classification, AI Extraction, Validation și Backend.
    """

    id: str
    file: str
    pages: int
    readable: bool
    type: str = "unknown"
    pages_data: list[PageExtract] = field(default_factory=list)
    unreadable_pages: list[int] = field(default_factory=list)
    has_injected_instructions: bool = False
    injection_flags: list[PromptInjectionFlag] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def document_id(self) -> str:
        """Alias pentru `id`, folosit în contractul Field din Sprint 1 (`document_id`)."""
        return self.id

    @property
    def page_map(self) -> dict[int, str]:
        """Dicționar {numar_pagina: text_pagina} pentru căutare și validare rapidă a citatelor."""
        return {p.page: p.text for p in self.pages_data}

    @property
    def page_strings(self) -> list[str]:
        """Listă de string-uri pe pagini (`pages[0]` = pagina 1, `""` pentru pagini ilizibile),
        exact în formatul cerut de `app/extraction` și `app/intake/classify.py`.
        """
        return [p.text if p.readable else "" for p in self.pages_data]

    @property
    def full_text(self) -> str:
        """Textul complet al documentului, gata pentru `classify_document(text)`."""
        parts: list[str] = []
        for p in self.pages_data:
            parts.append(f"--- PAGE {p.page} ---\n{p.text}")
        return "\n\n".join(parts)

    def to_contract_document(self) -> dict[str, Any]:
        """Returnează strict forma Document din docs/CONTRACT.md (`app/models.py`)."""
        return {
            "id": self.id,
            "type": self.type,
            "file": self.file,
            "pages": self.pages,
            "readable": self.readable,
        }

    def to_dict(self) -> dict[str, Any]:
        """Returnează dicționarul complet serializabil JSON pentru pipeline."""
        pages_list = [p.to_dict() for p in self.pages_data]
        return {
            "id": self.id,
            "document_id": self.id,
            "type": self.type,
            "file": self.file,
            "pages": self.pages,
            "readable": self.readable,
            "unreadable_pages": list(self.unreadable_pages),
            "pages_data": pages_list,
            "pages_text": pages_list,
            "page_strings": self.page_strings,
            "page_map": self.page_map,
            "full_text": self.full_text,
            "has_injected_instructions": self.has_injected_instructions,
            "injection_flags": [f.to_dict() for f in self.injection_flags],
            "warnings": list(self.warnings),
            "error": self.error,
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)
