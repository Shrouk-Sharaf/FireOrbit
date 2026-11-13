"""Create section-aware LangChain chunks from preprocessed PDF report JSON."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT_DIR / "data_processed" / "extracted_pdf_reports.json"
DEFAULT_OUTPUT = ROOT_DIR / "data_processed" / "rag_chunks.json"

# Match common standalone report headings. Parsing is performed on full_text rather
# than the shorter `sections` preview fields emitted by extract_pdfs.py.
HEADING_RE = re.compile(
    r"(?im)^\s*(abstract|introduction|background|objective[s]?|purpose|scope|"
    r"method[s]?|methodology|experimental(?:\s+(?:setup|procedure))?|"
    r"results?(?:\s+and\s+discussion)?|discussion|conclusions?|summary|"
    r"recommendations?|references|acknowledg(?:e)?ments?)\s*:?\s*$"
)


def load_reports(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a report dictionary in {path}")
    return payload


def split_into_sections(text: str) -> list[dict[str, Any]]:
    """Split full report text on recognized standalone headings, retaining offsets."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [{"section": "Document body", "text": text.strip(), "start": 0}]

    sections: list[dict[str, Any]] = []
    preamble = text[:matches[0].start()].strip()
    if preamble:
        sections.append({"section": "Preamble", "text": preamble, "start": 0})

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append({
                "section": match.group(1).strip().title(),
                "text": body,
                "start": start + (len(text[start:end]) - len(text[start:end].lstrip())),
            })
    return sections


def page_for_offset(pages: list[dict[str, Any]], offset: int) -> int | None:
    """Map a character offset in concatenated page text to a 1-based source page."""
    cursor = 0
    for page in pages:
        page_text = str(page.get("text") or "")
        page_end = cursor + len(page_text)
        if offset <= page_end:
            try:
                return int(page.get("page"))
            except (TypeError, ValueError):
                return None
        cursor = page_end + 2  # full_text joins pages with two newlines
    return int(pages[-1]["page"]) if pages and pages[-1].get("page") is not None else None


def build_chunks(
    reports: dict[str, Any], chunk_size: int = 1800, chunk_overlap: int = 250
) -> list[Document]:
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Require chunk_size > chunk_overlap >= 0")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
        strip_whitespace=True,
    )
    chunks: list[Document] = []

    for report_key, report in reports.items():
        full_text = str(report.get("full_text") or "").strip()
        if not full_text:
            continue
        sections = split_into_sections(full_text)
        pages = report.get("pages") or []
        for section in sections:
            base_offset = section["start"]
            section_doc = Document(
                page_content=section["text"],
                metadata={
                    "source": report.get("relative_path") or report_key,
                    "filename": report.get("filename") or report_key,
                    "psi_id": report.get("psi_id"),
                    "investigation_folder": report.get("investigation_folder"),
                    "source_type": report.get("source_type"),
                    "section": section["section"],
                },
            )
            for chunk in splitter.split_documents([section_doc]):
                local_start = int(chunk.metadata.pop("start_index", 0))
                global_start = base_offset + local_start
                global_end = global_start + len(chunk.page_content)
                start_page = page_for_offset(pages, global_start)
                end_page = page_for_offset(pages, global_end)
                chunk.metadata.update({
                    "chunk_index": len(chunks),
                    "page_start": start_page,
                    "page_end": end_page,
                    "char_start": global_start,
                    "char_end": global_end,
                })
                chunks.append(chunk)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunk-size", type=int, default=1800, help="Target size in characters")
    parser.add_argument("--chunk-overlap", type=int, default=250, help="Overlap in characters")
    args = parser.parse_args()

    docs = build_chunks(load_reports(args.input), args.chunk_size, args.chunk_overlap)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = [
        {"text": doc.page_content, "metadata": doc.metadata}
        for doc in docs
    ]
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {len(output)} section-aware chunks to {args.output}")


if __name__ == "__main__":
    main()
