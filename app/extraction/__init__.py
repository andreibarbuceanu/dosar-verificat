"""AI Extraction (pipeline step 4): document pages + type -> verified Fields."""
from .extract import ExtractionResult, extract_document
from .fields import COMMON, DOC_TYPES, PEOPLE, PERSON_KINDS, SPECIFIC, FieldSpec, fields_for
from .pdf import extract_pages, extract_pdf
from .prompt import PROMPT_VERSION, build_prompt, build_schema

__all__ = [
    "COMMON", "DOC_TYPES", "PEOPLE", "PERSON_KINDS", "PROMPT_VERSION", "SPECIFIC",
    "ExtractionResult", "FieldSpec", "build_prompt", "build_schema", "extract_document",
    "extract_pages", "extract_pdf", "fields_for",
]
