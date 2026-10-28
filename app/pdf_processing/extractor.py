from __future__ import annotations

import importlib
import io
import re
import unicodedata
from pathlib import Path
from typing import Any, BinaryIO

from .models import PageExtract, ProcessedDocument, PromptInjectionFlag


def _load_optional_module(module_name: str) -> Any:
    """Încarcă dinamic un modul opțional fără a genera erori de analiză statică în IDE/Pylance."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


# PyMuPDF 2 exposes the preferred ``pymupdf`` name; older releases use
# ``fitz``.  Supporting both keeps the declared >=1.24 dependency compatible.
fitz = _load_optional_module("pymupdf") or _load_optional_module("fitz")
_pypdf_mod = _load_optional_module("pypdf")
PdfReader = getattr(_pypdf_mod, "PdfReader", None) if _pypdf_mod is not None else None

# Pragul minim de caractere utile (fără spații) pentru ca o pagină să fie considerată lizibilă (R14)
DEFAULT_MIN_CHARS_PER_PAGE = 15

# Pattern-uri pentru detectarea instrucțiunilor ascunse / Prompt Injection (Regula R15)
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+|previous\s+|the\s+)?(rules|instructions|constraints)", re.IGNORECASE),
    re.compile(r"approve\s+this\s+(file|case|application|credit|loan)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+|previous\s+|the\s+)?(rules|instructions)", re.IGNORECASE),
    re.compile(r"system\s*prompt|override\s+rules|bypass\s+validation", re.IGNORECASE),
    re.compile(r"ignor[aă]\s+(toate\s+|anterioarele\s+)?(regulile|instruc[tț]iunile)", re.IGNORECASE),
    re.compile(r"aprob[aă]\s+(acest\s+)?(dosar|credit|fi[sș]ier)", re.IGNORECASE),
    re.compile(r"mark\s+(all\s+)?(rules|findings|case)\s+as\s+(pass|green)", re.IGNORECASE),
]


def _is_white_or_near_white(color_int: int | None) -> bool:
    """Verifică dacă o culoare RGB (int 0xRRGGBB din PyMuPDF) este albă sau aproape albă."""
    if color_int is None:
        return False
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return r >= 245 and g >= 245 and b >= 245


def _clean_text(raw_text: str) -> str:
    """Curăță caracterele invizibile și normalizează spațiile fără a altera structura rândurilor."""
    if not raw_text:
        return ""
    cleaned = (
        raw_text.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    result_lines: list[str] = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty and result_lines:
                result_lines.append("")
            prev_empty = True
        else:
            result_lines.append(line)
            prev_empty = False
    return "\n".join(result_lines).strip()


def _normalize_for_match(text: str) -> str:
    """Normalizează diacriticele românești (ș/ş, ț/ţ), ghilimelele și spațiile pentru verificarea citatelor."""
    if not text:
        return ""
    translation = str.maketrans(
        {
            "ş": "ș",
            "Ş": "Ș",
            "ţ": "ț",
            "Ţ": "Ț",
            "„": '"',
            "”": '"',
            "“": '"',
            "’": "'",
            "‘": "'",
            "\xa0": " ",
            "\u2013": "-",
            "\u2014": "-",
        }
    )
    norm = text.translate(translation)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def _strip_accents(text: str) -> str:
    """Elimină complet diacriticele pentru fallback în caz de encoding diferit în PDF."""
    norm = _normalize_for_match(text)
    return "".join(
        ch for ch in unicodedata.normalize("NFD", norm) if unicodedata.category(ch) != "Mn"
    )


def _scan_text_for_injection_patterns(
    raw_page_text: str,
    page_number: int,
    seen_snippets: set[str],
    flags: list[PromptInjectionFlag],
) -> None:
    """Scanează textul brut după expresii de tip prompt injection (R15)."""
    for line in raw_page_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        for pattern in INJECTION_PATTERNS:
            if pattern.search(line_clean):
                key = line_clean.lower()
                if key not in seen_snippets:
                    seen_snippets.add(key)
                    flags.append(
                        PromptInjectionFlag(
                            page=page_number,
                            reason="instruction_pattern",
                            snippet=line_clean,
                        )
                    )
                break


def _inspect_fitz_page(
    page: Any, page_number: int
) -> tuple[list[str], list[PromptInjectionFlag]]:
    """Inspectează span-urile paginii (PyMuPDF) pentru text ascuns (alb / microscopic) și instrucțiuni (R15)."""
    hidden_texts: list[str] = []
    flags: list[PromptInjectionFlag] = []
    seen_snippets: set[str] = set()

    try:
        page_dict = page.get_text("dict")
    except Exception:
        page_dict = {"blocks": []}

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = (span.get("text") or "").strip()
                if not span_text:
                    continue
                color = span.get("color")
                size = float(span.get("size", 10.0))

                is_white = _is_white_or_near_white(color)
                is_tiny = size <= 2.0

                if is_white or is_tiny:
                    hidden_texts.append(span_text)
                    reason = "hidden_white_text" if is_white else "tiny_hidden_text"
                    if len(span_text) >= 4 and span_text.lower() not in seen_snippets:
                        seen_snippets.add(span_text.lower())
                        flags.append(
                            PromptInjectionFlag(
                                page=page_number,
                                reason=reason,
                                snippet=span_text,
                            )
                        )

    raw_page_text = page.get_text("text") or ""
    _scan_text_for_injection_patterns(raw_page_text, page_number, seen_snippets, flags)
    return hidden_texts, flags


def _sanitize_injected_text(
    text: str, hidden_texts: list[str], flags: list[PromptInjectionFlag]
) -> str:
    """Elimină instrucțiunile injectate / textul alb ascuns din textul livrat către AI (R15: instruction ignored)."""
    if not text:
        return ""
    sanitized = text
    to_remove = set(hidden_texts) | {f.snippet for f in flags}
    for snippet in sorted(to_remove, key=len, reverse=True):
        if snippet and len(snippet) >= 4:
            sanitized = sanitized.replace(snippet, "")
    kept_lines: list[str] = []
    for line in sanitized.splitlines():
        if any(p.search(line) for p in INJECTION_PATTERNS):
            continue
        kept_lines.append(line)
    return _clean_text("\n".join(kept_lines))


def _resolve_source_bytes_and_names(
    source: str | Path | bytes | BinaryIO,
) -> tuple[bytes, str, str]:
    """Returnează (raw_pdf_bytes, filename, default_doc_id) din orice tip de sursă."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Fișierul PDF nu există: {path}")
        return path.read_bytes(), path.name, path.stem

    if isinstance(source, (bytes, bytearray)):
        return bytes(source), "uploaded.pdf", "uploaded_doc"

    if hasattr(source, "read"):
        raw = source.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        name = getattr(source, "name", "uploaded.pdf")
        stem = Path(str(name)).stem or "uploaded_doc"
        return raw, Path(str(name)).name, stem

    raise TypeError(f"Tip de sursă PDF nesuportat: {type(source)!r}")


def _process_with_pypdf(
    raw_bytes: bytes,
    final_id: str,
    filename: str,
    document_type: str,
    min_chars_per_page: int,
) -> ProcessedDocument:
    """Procesare PDF folosind `pypdf` (fallback când `fitz` nu este instalat)."""
    if PdfReader is None:
        raise RuntimeError("Modulul pypdf nu este disponibil.")
    reader = PdfReader(io.BytesIO(raw_bytes))
    total_pages = len(reader.pages)
    if total_pages == 0:
        return ProcessedDocument(
            id=final_id,
            file=filename,
            pages=0,
            readable=False,
            type=document_type,
            warnings=["Documentul PDF nu conține nicio pagină."],
            error="Empty PDF (0 pages)",
        )

    pages_data: list[PageExtract] = []
    unreadable_pages: list[int] = []
    all_injection_flags: list[PromptInjectionFlag] = []
    warnings: list[str] = []

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        hidden_texts: list[str] = []
        page_flags: list[PromptInjectionFlag] = []
        seen_snippets: set[str] = set()

        raw_text = page.extract_text() or ""

        try:
            content_obj = page.get_contents()
            content_bytes = content_obj.get_data() if content_obj else b""
            content_str = content_bytes.decode("latin-1", errors="ignore")
            for m in re.finditer(
                r"(?:1(?:\.0+)?\s+1(?:\.0+)?\s+1(?:\.0+)?\s+rg|1(?:\.0+)?\s+g)\s*.*?\(([^)]{4,})\)\s*Tj",
                content_str,
                re.DOTALL,
            ):
                txt_cand = m.group(1).strip()
                if txt_cand:
                    hidden_texts.append(txt_cand)
                    if txt_cand.lower() not in seen_snippets:
                        seen_snippets.add(txt_cand.lower())
                        page_flags.append(
                            PromptInjectionFlag(
                                page=page_num,
                                reason="hidden_white_text",
                                snippet=txt_cand,
                            )
                        )
        except Exception:
            pass

        _scan_text_for_injection_patterns(raw_text, page_num, seen_snippets, page_flags)
        all_injection_flags.extend(page_flags)

        clean_page_text = _sanitize_injected_text(raw_text, hidden_texts, page_flags)
        non_ws_chars = len(re.sub(r"\s+", "", clean_page_text))

        try:
            has_images = len(page.images) > 0
        except Exception:
            try:
                resources = page.get("/Resources") or {}
                xobj = resources.get("/XObject") or {}
                has_images = len(xobj) > 0
            except Exception:
                has_images = False

        page_readable = non_ws_chars >= min_chars_per_page
        is_scanned_only = not page_readable

        if not page_readable:
            unreadable_pages.append(page_num)
            if has_images:
                warnings.append(
                    f"Pagina {page_num} este scanată (imagine fără strat de text / OCR) și este ilizibilă (R14)."
                )
            else:
                warnings.append(
                    f"Pagina {page_num} nu conține suficient text lizibil ({non_ws_chars} caractere) (R14)."
                )

        for flag in page_flags:
            warnings.append(
                f"Alerte de securitate (R15) pe pagina {page_num} ({flag.reason}): '{flag.snippet}'"
            )

        pages_data.append(
            PageExtract(
                page=page_num,
                text=clean_page_text,
                readable=page_readable,
                char_count=non_ws_chars,
                has_images=has_images,
                is_scanned_only=is_scanned_only,
                hidden_texts=hidden_texts,
            )
        )

    doc_readable = total_pages > 0 and len(unreadable_pages) == 0
    return ProcessedDocument(
        id=final_id,
        file=filename,
        pages=total_pages,
        readable=doc_readable,
        type=document_type,
        pages_data=pages_data,
        unreadable_pages=unreadable_pages,
        has_injected_instructions=len(all_injection_flags) > 0,
        injection_flags=all_injection_flags,
        warnings=warnings,
        error=None,
    )


def process_pdf_model(
    source: str | Path | bytes | BinaryIO,
    document_id: str | None = None,
    document_type: str = "unknown",
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> ProcessedDocument:
    """Procesează un document PDF și returnează obiectul `ProcessedDocument`."""
    fallback_file = str(source) if isinstance(source, (str, Path)) else "uploaded.pdf"
    fallback_id = (
        document_id
        or (Path(source).stem if isinstance(source, (str, Path)) else "uploaded_doc")
    )

    try:
        raw_bytes, filename, inferred_id = _resolve_source_bytes_and_names(source)
    except Exception as exc:
        return ProcessedDocument(
            id=fallback_id,
            file=Path(fallback_file).name,
            pages=0,
            readable=False,
            type=document_type,
            pages_data=[],
            unreadable_pages=[],
            warnings=[f"Documentul PDF nu a putut fi citit: {exc}"],
            error=str(exc),
        )

    final_id = document_id or inferred_id

    if fitz is None:
        try:
            return _process_with_pypdf(
                raw_bytes=raw_bytes,
                final_id=final_id,
                filename=filename,
                document_type=document_type,
                min_chars_per_page=min_chars_per_page,
            )
        except Exception as exc:
            return ProcessedDocument(
                id=final_id,
                file=filename,
                pages=0,
                readable=False,
                type=document_type,
                warnings=[f"Documentul PDF este corupt sau invalid: {exc}"],
                error=str(exc),
            )

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:
        return ProcessedDocument(
            id=final_id,
            file=filename,
            pages=0,
            readable=False,
            type=document_type,
            pages_data=[],
            unreadable_pages=[],
            warnings=[f"Documentul PDF nu a putut fi deschis: {exc}"],
            error=str(exc),
        )

    pages_data: list[PageExtract] = []
    unreadable_pages: list[int] = []
    all_injection_flags: list[PromptInjectionFlag] = []
    warnings: list[str] = []

    try:
        total_pages = len(doc)
        if total_pages == 0:
            warnings.append("Documentul PDF nu conține nicio pagină.")
            return ProcessedDocument(
                id=final_id,
                file=filename,
                pages=0,
                readable=False,
                type=document_type,
                warnings=warnings,
                error="Empty PDF (0 pages)",
            )

        for idx in range(total_pages):
            page_num = idx + 1
            page = doc[idx]

            raw_text = page.get_text("text") or ""
            hidden_texts, page_flags = _inspect_fitz_page(page, page_num)
            all_injection_flags.extend(page_flags)

            clean_page_text = _sanitize_injected_text(raw_text, hidden_texts, page_flags)
            non_ws_chars = len(re.sub(r"\s+", "", clean_page_text))

            try:
                images = page.get_images(full=True)
                has_images = len(images) > 0
            except Exception:
                has_images = False

            page_readable = non_ws_chars >= min_chars_per_page
            is_scanned_only = not page_readable

            if not page_readable:
                unreadable_pages.append(page_num)
                if has_images:
                    warnings.append(
                        f"Pagina {page_num} este scanată (imagine fără strat de text / OCR) și este ilizibilă (R14)."
                    )
                else:
                    warnings.append(
                        f"Pagina {page_num} nu conține suficient text lizibil ({non_ws_chars} caractere) (R14)."
                    )

            for flag in page_flags:
                warnings.append(
                    f"Alerte de securitate (R15) pe pagina {page_num} ({flag.reason}): '{flag.snippet}'"
                )

            pages_data.append(
                PageExtract(
                    page=page_num,
                    text=clean_page_text,
                    readable=page_readable,
                    char_count=non_ws_chars,
                    has_images=has_images,
                    is_scanned_only=is_scanned_only,
                    hidden_texts=hidden_texts,
                )
            )
    finally:
        doc.close()

    doc_readable = total_pages > 0 and len(unreadable_pages) == 0

    return ProcessedDocument(
        id=final_id,
        file=filename,
        pages=total_pages,
        readable=doc_readable,
        type=document_type,
        pages_data=pages_data,
        unreadable_pages=unreadable_pages,
        has_injected_instructions=len(all_injection_flags) > 0,
        injection_flags=all_injection_flags,
        warnings=warnings,
        error=None,
    )


def process_pdf(
    source: str | Path | bytes | BinaryIO,
    document_id: str | None = None,
    document_type: str = "unknown",
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> dict[str, Any]:
    """Funcția principală: procesează un PDF și returnează dicționarul JSON conform contractului."""
    return process_pdf_model(
        source=source,
        document_id=document_id,
        document_type=document_type,
        min_chars_per_page=min_chars_per_page,
    ).to_dict()


def process_multiple_pdfs(
    sources: list[str | Path | bytes | BinaryIO | dict[str, Any]],
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> list[dict[str, Any]]:
    """Procesează o listă de documente PDF (minimum 3 sau oricâte are dosarul)."""
    results: list[dict[str, Any]] = []
    for idx, item in enumerate(sources, start=1):
        if isinstance(item, dict):
            src = item.get("file") or item.get("path") or item.get("source")
            doc_id = item.get("id") or item.get("document_id")
            doc_type = item.get("type", "unknown")
            results.append(
                process_pdf(
                    source=src,
                    document_id=doc_id,
                    document_type=doc_type,
                    min_chars_per_page=min_chars_per_page,
                )
            )
        else:
            default_id = (
                Path(item).stem
                if isinstance(item, (str, Path))
                else f"doc_{idx:03d}"
            )
            results.append(
                process_pdf(
                    source=item,
                    document_id=default_id,
                    min_chars_per_page=min_chars_per_page,
                )
            )
    return results


def extract_pages(
    source: str | Path | bytes | BinaryIO,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> list[PageExtract]:
    """Funcția din docs/CONTRACT.md: `extract_pages(path) -> list[Page]` (text per page, readable flag).

    Fiecare element `Page` are `.page` (1-based), `.text` (str), `.readable` (bool) și suportă
    și acces de tip dicționar `page["text"]`, `page["readable"]`.
    """
    model = process_pdf_model(source=source, min_chars_per_page=min_chars_per_page)
    return list(model.pages_data)


def extract_page_strings(
    source: str | Path | bytes | BinaryIO,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> list[str]:
    """Returnează `list[str]` cu textul fiecărei pagini (`""` pentru paginile ilizibile/scanate),
    direct compatibil cu `app.extraction.extract_document(doc_id, doc_type, pages)`.
    """
    model = process_pdf_model(source=source, min_chars_per_page=min_chars_per_page)
    return model.page_strings


def extract_text_by_page(
    source: str | Path | bytes | BinaryIO,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> list[dict[str, Any]]:
    """Returnează direct lista de pagini extrase ca dict: `[{"page": 1, "text": "...", "readable": True, ...}]`."""
    model = process_pdf_model(source=source, min_chars_per_page=min_chars_per_page)
    return [p.to_dict() for p in model.pages_data]


def verify_quote_on_page(
    processed_doc: dict[str, Any] | ProcessedDocument,
    page: int,
    quote: str,
) -> bool:
    """Verifică în cod dacă `quote` există pe pagina `page` a documentului procesat."""
    if not quote or not quote.strip() or page < 1:
        return False

    if isinstance(processed_doc, ProcessedDocument):
        page_map = processed_doc.page_map
    else:
        page_map = processed_doc.get("page_map") or {}
        if not page_map:
            for p in processed_doc.get("pages_data") or processed_doc.get("pages_text") or []:
                page_map[int(p["page"])] = p.get("text", "")

    page_text = page_map.get(page) or page_map.get(str(page))  # type: ignore[arg-type]
    if not page_text:
        return False

    if quote in page_text:
        return True

    norm_quote = _normalize_for_match(quote)
    norm_page = _normalize_for_match(page_text)
    if norm_quote and norm_quote in norm_page:
        return True

    ascii_quote = _strip_accents(quote).lower()
    ascii_page = _strip_accents(page_text).lower()
    if ascii_quote and ascii_quote in ascii_page:
        return True

    return False


def render_page_to_png(
    source: str | Path | bytes | BinaryIO,
    page_number: int,
    highlight_quote: str | None = None,
    dpi: int = 150,
) -> bytes:
    """Randează pagina `page_number` (1-indexed) ca imagine PNG (bytes)."""
    if page_number < 1:
        raise ValueError("Numărul paginii trebuie să fie >= 1.")

    raw_bytes, _, _ = _resolve_source_bytes_and_names(source)

    if fitz is not None:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        try:
            if page_number > len(doc):
                raise IndexError(
                    f"Pagina {page_number} nu există în document (total pagini: {len(doc)})."
                )
            page = doc[page_number - 1]

            if highlight_quote and highlight_quote.strip():
                rects = page.search_for(highlight_quote.strip())
                if not rects:
                    words = highlight_quote.strip().split()
                    if len(words) >= 3:
                        short_query = " ".join(words[:4])
                        rects = page.search_for(short_query)
                for rect in rects:
                    annot = page.add_highlight_annot(rect)
                    annot.set_colors(stroke=(1.0, 0.92, 0.23))
                    annot.update()

            pix = page.get_pixmap(dpi=dpi)
            return pix.tobytes("png")
        finally:
            doc.close()

    pil_image = _load_optional_module("PIL.Image")
    pil_draw = _load_optional_module("PIL.ImageDraw")
    if pil_image is None or pil_draw is None:
        raise RuntimeError("Nici PyMuPDF (fitz), nici Pillow nu sunt disponibile pentru randare PNG.")

    doc_model = process_pdf_model(raw_bytes)
    if page_number > doc_model.pages:
        raise IndexError(
            f"Pagina {page_number} nu există în document (total pagini: {doc_model.pages})."
        )
    page_text = doc_model.page_map.get(page_number, "")
    img = pil_image.new("RGB", (800, 1100), color=(255, 255, 255))
    draw = pil_draw.Draw(img)
    y = 40
    for line in page_text.splitlines():
        if highlight_quote and highlight_quote.strip() and highlight_quote.strip() in line:
            draw.rectangle([(35, y - 2), (760, y + 18)], fill=(255, 245, 157))
        draw.text((40, y), line, fill=(20, 20, 20))
        y += 22
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
