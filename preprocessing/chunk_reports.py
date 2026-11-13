"""Build validated, section-aware recursive chunks for FireOrbit PDF reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT_DIR / "data_processed" / "extracted_pdf_reports.json"
DEFAULT_OUTPUT = ROOT_DIR / "data_processed" / "rag_chunks.json"
DEFAULT_CHUNK_SIZE = 1800
DEFAULT_CHUNK_OVERLAP = 250
SMALL_CHUNK_THRESHOLD = 200

# Only complete lines matching a known report heading are recognized. Restricting
# the title to known NASA/scientific/combustion headings avoids treating arbitrary
# numbered prose, table rows, or bibliography entries as section boundaries.
_HEADING_NAMES = (
    r"abstract|executive\s+summary|introduction|background|literature\s+review|"
    r"objective[s]?|purpose|scope|approach|hypoth(?:e|a)sis(?:es)?|"
    r"method(?:s|ology)?|experimental(?:\s+(?:program|apparatus|setup|procedure|method|conditions))?|"
    r"test\s+(?:program|apparatus|conditions|matrix|procedure)|"
    r"materials?(?:\s+and\s+methods)?|fuel(?:s|\s+properties)?|"
    r"combustion(?:\s+(?:research|experiments?|characteristics|results|model))?|"
    r"fire\s+(?:safety|behavior|behaviour|growth|suppression|detection)|"
    r"flammability|flame(?:\s+(?:spread|retardancy|structure|behavior|behaviour|characteristics|results))?|"
    r"ignition|burning(?:\s+(?:rate|behavior|behaviour|characteristics))?|"
    r"extinction|soot(?:\s+(?:formation|measurements?))?|smoke(?:\s+(?:production|measurements?))?|"
    r"droplet(?:\s+(?:combustion|burning|experiments?))?|microgravity|reduced\s+gravity|"
    r"oxygen(?:\s+(?:concentration|enrichment|level))?|results?(?:\s+and\s+discussion)?|"
    r"discussion|conclusions?|summary|recommendations?|future\s+work|references|"
    r"acknowledg(?:e)?ments?|appendix(?:\s+[a-z0-9]+)?"
)
HEADING_RE = re.compile(
    rf"^[ \t]*(?P<number>\d+(?:\.\d+)*(?:[.)])?[ \t]+)?"
    rf"(?P<title>{_HEADING_NAMES})[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def load_reports(path: Path) -> dict[str, Any]:
    """Load preprocessed report mapping and validate its top-level shape."""
    if not path.is_file():
        raise FileNotFoundError(f"Input report JSON does not exist: {path}")
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object keyed by report in {path}")
    return payload


def split_into_sections(text: str) -> list[dict[str, Any]]:
    """Split raw report text into recognized headings, preserving exact offsets."""
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        start = len(text) - len(text.lstrip())
        body = text.strip()
        return [{"section": "full_document", "text": body, "start": start}] if body else []

    sections: list[dict[str, Any]] = []
    preamble = text[:matches[0].start()]
    if preamble.strip():
        start = len(preamble) - len(preamble.lstrip())
        sections.append({"section": "Preamble", "text": preamble.strip(), "start": start})

    for index, match in enumerate(matches):
        raw_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_body = text[match.end():raw_end]
        body = raw_body.strip()
        if not body:
            continue
        body_start = match.end() + (len(raw_body) - len(raw_body.lstrip()))
        title = " ".join(match.group("title").split())
        number = " ".join((match.group("number") or "").split())
        section_name = f"{number} {title}".strip()
        sections.append({"section": section_name, "text": body, "start": body_start})
    return sections


def _page_ranges(pages: Any, full_text: str) -> list[tuple[int, int, int]]:
    """Return (full-text start, full-text end, page number) using exact page text offsets."""
    if not isinstance(pages, list):
        return []
    ranges: list[tuple[int, int, int]] = []
    cursor = 0
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("text"), str):
            continue
        try:
            page_number = int(page["page"])
        except (KeyError, TypeError, ValueError):
            continue
        page_text = page["text"]
        # Prefer exact positional mapping when extracted pages reconstruct full_text.
        if full_text[cursor:cursor + len(page_text)] != page_text:
            candidate = full_text.find(page_text, cursor)
            if candidate < 0:
                continue
            cursor = candidate
        start = cursor
        end = start + len(page_text)
        ranges.append((start, end, page_number))
        cursor = end + 2
    return ranges


def _page_at(offset: int, ranges: list[tuple[int, int, int]]) -> int | None:
    for start, end, page in ranges:
        if start <= offset <= end:
            return page
    return None


def _chroma_scalar(value: Any) -> str | int | float | bool | None:
    """Keep metadata to Chroma-compatible scalar values; stringify complex values."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _chunk_id(source: str, section: str, start: int, text: str) -> str:
    identity = "\0".join((source, section, str(start), text))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _rebalance_short_tail(
    section_docs: list[Document],
    source_text: str,
    page_ranges: list[tuple[int, int, int]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """Redistribute a tiny trailing chunk over its predecessor when safe."""
    if len(section_docs) < 2 or len(section_docs[-1].page_content) >= SMALL_CHUNK_THRESHOLD:
        return section_docs
    previous, tail = section_docs[-2:]
    if previous.metadata.get("section") != tail.metadata.get("section"):
        return section_docs
    first_start = previous.metadata["char_start"]
    last_end = tail.metadata["char_end"]
    overlap = min(chunk_overlap, max(0, chunk_size // 4))
    low_cut = max(first_start + SMALL_CHUNK_THRESHOLD - overlap // 2,
                  last_end - chunk_size + overlap // 2)
    high_cut = min(first_start + chunk_size - overlap // 2,
                   last_end - SMALL_CHUNK_THRESHOLD + overlap // 2)
    if low_cut > high_cut:
        return section_docs

    # Candidate cut points are whitespace boundaries; this preserves whole words
    # and avoids arbitrary splits in formulas, units, or scientific notation.
    candidates = [i for i in range(max(first_start + 1, low_cut), min(last_end, high_cut + 1))
                  if source_text[i - 1:i].isspace() or source_text[i:i + 1].isspace()]
    if not candidates:
        return section_docs
    target = (low_cut + high_cut) // 2
    cut = min(candidates, key=lambda value: abs(value - target))
    left_end = cut + overlap // 2
    right_start = left_end - overlap
    if left_end <= first_start or right_start >= last_end:
        return section_docs
    left_text = source_text[first_start:left_end]
    right_text = source_text[right_start:last_end]
    if not left_text.strip() or not right_text.strip() or max(len(left_text), len(right_text)) > chunk_size:
        return section_docs

    for doc, start, end, text in (
        (previous, first_start, left_end, left_text),
        (tail, right_start, last_end, right_text),
    ):
        doc.page_content = text
        doc.metadata.update({
            "char_start": start,
            "char_end": end,
            "page_start": _page_at(start, page_ranges) if _page_at(start, page_ranges) is not None else "",
            "page_end": _page_at(max(start, end - 1), page_ranges) if _page_at(max(start, end - 1), page_ranges) is not None else "",
        })
        doc.metadata["chunk_id"] = _chunk_id(doc.metadata["source"], doc.metadata["section"], start, text)
    return section_docs


def _source_metadata(report_key: str, report: dict[str, Any], source: str, section: str) -> dict[str, Any]:
    report_id = report.get("report_id") or report.get("psi_id") or report_key
    # Keep useful identifiers/context from the existing extractor schema, while
    # excluding bulky text fields. Missing page values become empty strings below
    # because Chroma does not accept None in metadata.
    values = {
        "source": source,
        "filename": report.get("filename") or Path(source).name or report_key,
        "report_id": report_id,
        "section": section,
        "psi_id": report.get("psi_id"),
        "investigation_folder": report.get("investigation_folder"),
        "source_type": report.get("source_type"),
        "relative_path": report.get("relative_path"),
    }
    return {
        key: scalar
        for key, value in values.items()
        if (scalar := _chroma_scalar(value)) is not None
    }


def validate_chunks(chunks: list[Document], sources: dict[str, str], chunk_size: int) -> None:
    """Raise on broken provenance, empty text, duplicate IDs, or invalid offsets."""
    seen: set[str] = set()
    for doc in chunks:
        text = doc.page_content
        meta = doc.metadata
        chunk_id = meta.get("chunk_id")
        if not text or not text.strip():
            raise ValueError("Generated an empty or whitespace-only chunk")
        if not chunk_id or chunk_id in seen:
            raise ValueError(f"Missing or duplicate chunk_id: {chunk_id!r}")
        seen.add(chunk_id)
        if not meta.get("section"):
            raise ValueError(f"Chunk {chunk_id} has no section metadata")
        if len(text) > chunk_size:
            raise ValueError(f"Chunk {chunk_id} exceeds configured size")
        source_text = sources.get(str(meta["source"]))
        if source_text is None:
            raise ValueError(f"No original text available for {meta['source']}")
        start, end = meta.get("char_start"), meta.get("char_end")
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start <= end <= len(source_text)):
            raise ValueError(f"Invalid character offsets in chunk {chunk_id}: {start}:{end}")
        if source_text[start:end] != text:
            raise ValueError(f"Chunk text does not match its source offsets: {chunk_id}")
        page_start, page_end = meta.get("page_start"), meta.get("page_end")
        if page_start != "" and (not isinstance(page_start, int) or page_start < 1):
            raise ValueError(f"Invalid page_start in chunk {chunk_id}")
        if page_end != "" and (not isinstance(page_end, int) or page_end < 1):
            raise ValueError(f"Invalid page_end in chunk {chunk_id}")
        if page_start != "" and page_end != "" and page_end < page_start:
            raise ValueError(f"Invalid page range in chunk {chunk_id}")
        if any(value is None or isinstance(value, (dict, list)) for value in meta.values()):
            raise ValueError(f"Non-scalar Chroma metadata in chunk {chunk_id}")


def build_chunks(
    reports: dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Create LangChain Documents independently within each detected section."""
    if not isinstance(reports, dict):
        raise TypeError("reports must be a dictionary keyed by report identifier")
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if not isinstance(chunk_overlap, int) or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be an integer in [0, chunk_size)")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", r"(?<=[.!?])\s+", " " , ""],
        is_separator_regex=True,
        keep_separator="end",
        add_start_index=True,
        strip_whitespace=True,
    )
    docs: list[Document] = []
    source_texts: dict[str, str] = {}

    for report_key, report in reports.items():
        if not isinstance(report, dict):
            print(f"Warning: skipping {report_key}: report record is not an object", file=sys.stderr)
            continue
        full_text = report.get("full_text")
        if not isinstance(full_text, str) or not full_text.strip():
            print(f"Warning: skipping {report_key}: missing or empty full_text", file=sys.stderr)
            continue

        source = str(report.get("relative_path") or report_key)
        source_texts[source] = full_text
        page_ranges = _page_ranges(report.get("pages"), full_text)
        for section in split_into_sections(full_text):
            base_metadata = _source_metadata(str(report_key), report, source, section["section"])
            section_doc = Document(page_content=section["text"], metadata=base_metadata)
            section_pieces = splitter.split_documents([section_doc])
            for piece in section_pieces:
                local_start = piece.metadata.pop("start_index", None)
                if not isinstance(local_start, int) or local_start < 0:
                    # Fallback is exact-content lookup within the section.
                    local_start = section["text"].find(piece.page_content)
                if local_start < 0:
                    raise ValueError(f"Could not locate chunk text in section {section['section']}")
                char_start = section["start"] + local_start
                char_end = char_start + len(piece.page_content)
                p_start = _page_at(char_start, page_ranges)
                p_end = _page_at(max(char_start, char_end - 1), page_ranges)
                piece.metadata.update({
                    "chunk_id": _chunk_id(source, section["section"], char_start, piece.page_content),
                    "page_start": p_start if p_start is not None else "",
                    "page_end": p_end if p_end is not None else "",
                    "char_start": char_start,
                    "char_end": char_end,
                })
                docs.append(piece)
            if section_pieces:
                section_docs = docs[-len(section_pieces):]
                rebalanced = _rebalance_short_tail(
                    section_docs, full_text, page_ranges, chunk_size, chunk_overlap
                )
                docs[-len(section_pieces):] = rebalanced

    validate_chunks(docs, source_texts, chunk_size)
    return docs


def _print_summary(chunks: list[Document], report_count: int, chunk_size: int) -> None:
    sizes = [len(doc.page_content) for doc in chunks]
    tiny = sum(size < SMALL_CHUNK_THRESHOLD for size in sizes)
    no_pages = sum(doc.metadata.get("page_start") == "" for doc in chunks)
    sections = {(doc.metadata["source"], doc.metadata["section"]) for doc in chunks}
    avg = (sum(sizes) / len(sizes)) if sizes else 0.0
    print(f"Reports processed: {report_count}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Chunk size (chars): avg {avg:.1f}, min {min(sizes, default=0)}, max {max(sizes, default=0)}; configured max {chunk_size}")
    print(f"Unusually small chunks (<{SMALL_CHUNK_THRESHOLD} chars; flagged for inspection): {tiny}")
    print(f"Chunks without page mapping: {no_pages}")
    print(f"Detected report sections: {len(sections)}")


def write_chunks(chunks: list[Document], output_path: Path) -> None:
    """Write a JSON array of text + scalar metadata records atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [{"text": doc.page_content, "metadata": doc.metadata} for doc in chunks]
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temp_path.replace(output_path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    args = parser.parse_args()

    try:
        reports = load_reports(args.input)
        chunks = build_chunks(reports, args.chunk_size, args.chunk_overlap)
        write_chunks(chunks, args.output)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    _print_summary(chunks, len(reports), args.chunk_size)
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
