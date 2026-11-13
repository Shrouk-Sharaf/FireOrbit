"""Create retrieval-friendly chunks from FireOrbit's processed JSON data.

Usage from the repository root:
    python preprocessing/recursive_chunking.py

The script uses only the Python standard library. It recursively splits report
and investigation prose using paragraph, line, sentence, word, then character
boundaries. Structured experiment rows remain intact as one record per chunk.

Report and investigation chunks shorter than --min-chunk-chars (default 150)
are dropped: they are almost always page numbers, running headers/footers,
appendix dividers or bare figure captions that add noise to retrieval.
Experiment records are never filtered.

Exact duplicate report/investigation chunks (same text ignoring case and
whitespace, e.g. repeated boilerplate) are also removed; the first occurrence
is kept. Disable with --keep-duplicates.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data_processed"
DEFAULT_OUTPUT = PROJECT_ROOT / "chunking" / "chunks.json"
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
DEFAULT_MIN_CHUNK_CHARS = 150


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def recursive_pieces(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Split text into pieces <= chunk_size, preferring larger boundaries first."""
    if len(text) <= chunk_size:
        return [text] if text else []

    if not separators:
        separators = [""]

    separator_index = next(
        (i for i, separator in enumerate(separators)
         if separator == "" or separator in text),
        len(separators) - 1,
    )
    separator = separators[separator_index]
    remaining_separators = separators[separator_index + 1 :]

    if separator == "":
        raw_pieces = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    else:
        # Keep delimiters attached to the preceding piece, so the original text
        # remains readable when pieces are joined back together.
        split_parts = text.split(separator)
        raw_pieces = [part + separator for part in split_parts[:-1]]
        if split_parts[-1]:
            raw_pieces.append(split_parts[-1])

    pieces: list[str] = []
    for piece in raw_pieces:
        if not piece:
            continue
        if len(piece) > chunk_size:
            pieces.extend(recursive_pieces(piece, chunk_size, remaining_separators))
        else:
            pieces.append(piece)
    return pieces


def recursive_character_chunks(
    text: str, chunk_size: int = 1000, overlap: int = 150
) -> list[str]:
    """Recursively split text and merge pieces into bounded, overlapping chunks."""
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    if not text:
        return []
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    pieces = recursive_pieces(text, chunk_size, DEFAULT_SEPARATORS)
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for piece in pieces:
        if current and current_length + len(piece) > chunk_size:
            previous = "".join(current)
            chunks.append(previous.strip())

            # Keep as much of the previous tail as fits beside the next piece.
            # This preserves overlap without allowing a chunk to exceed size.
            allowed_overlap = min(overlap, chunk_size - len(piece))
            tail = previous[-allowed_overlap:] if allowed_overlap else ""
            current = [tail] if tail else []
            current_length = len(tail)

        # A piece larger than the limit should not occur, but guard against it
        # so this function stays safe if the separator implementation changes.
        if len(piece) > chunk_size:
            for start in range(0, len(piece), chunk_size):
                fragment = piece[start : start + chunk_size]
                if current:
                    previous = "".join(current)
                    chunks.append(previous.strip())
                    allowed_overlap = min(overlap, chunk_size - len(fragment))
                    tail = previous[-allowed_overlap:] if allowed_overlap else ""
                    current = [tail] if tail else []
                    current_length = len(tail)
                current.append(fragment)
                current_length += len(fragment)
                if current_length >= chunk_size:
                    chunks.append("".join(current).strip())
                    allowed_overlap = min(overlap, chunk_size - len(fragment))
                    tail = "".join(current)[-allowed_overlap:] if allowed_overlap else ""
                    current = [tail] if tail else []
                    current_length = len(tail)
            continue

        current.append(piece)
        current_length += len(piece)

    if current:
        final_chunk = "".join(current).strip()
        if final_chunk:
            chunks.append(final_chunk)

    return [chunk for chunk in chunks if chunk]


def clean_component(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(clean_component(item) for item in value if item is not None)
    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {clean_component(item)}"
            for key, item in value.items()
            if item is not None and item != ""
        )
    return str(value).strip()


def make_chunk(
    *,
    text: str,
    source_file: str,
    source_id: str,
    chunk_index: int,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chunk_id": f"{source_id}::chunk-{chunk_index:04d}",
        "text": text,
        "metadata": {
            "source_file": source_file,
            "source_id": source_id,
            "chunk_index": chunk_index,
            **metadata,
        },
    }


def split_document(
    text: str,
    *,
    source_file: str,
    source_id: str,
    metadata: dict[str, Any],
    chunk_size: int,
    overlap: int,
    min_chars: int = 0,
    stats: Counter | None = None,
) -> list[dict[str, Any]]:
    texts = recursive_character_chunks(text, chunk_size, overlap)

    # Drop tiny chunks (page numbers, headers/footers, bare captions) before
    # numbering, so chunk_index stays contiguous within each source.
    kept = [t for t in texts if len(t) >= min_chars]
    if stats is not None:
        stats["dropped_short"] += len(texts) - len(kept)

    return [
        make_chunk(
            text=chunk_text,
            source_file=source_file,
            source_id=source_id,
            chunk_index=index,
            metadata=metadata,
        )
        for index, chunk_text in enumerate(kept, start=1)
    ]


def remove_duplicate_chunks(
    chunks: list[dict[str, Any]], stats: Counter
) -> list[dict[str, Any]]:
    """Drop exact duplicate texts (ignoring case/whitespace), keeping the first.

    Experiment records are skipped: each one is a distinct record.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for chunk in chunks:
        if chunk["metadata"].get("document_type") == "experiment_record":
            unique.append(chunk)
            continue
        key = re.sub(r"\s+", " ", chunk["text"]).strip().lower()
        if key in seen:
            stats["dropped_duplicate"] += 1
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def chunks_from_reports(
    data_dir: Path, chunk_size: int, overlap: int, min_chars: int, stats: Counter
) -> list[dict[str, Any]]:
    path = data_dir / "extracted_pdf_reports.json"
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return []

    reports = load_json(path)
    output: list[dict[str, Any]] = []
    for report_key, report in reports.items():
        relative_path = report.get("relative_path") or report_key
        source_id = relative_path
        common_metadata = {
            "document_type": "report",
            "filename": report.get("filename"),
            "relative_path": relative_path,
            "psi_id": report.get("psi_id"),
            "source_type": report.get("source_type"),
        }

        pages = report.get("pages") or []
        if pages:
            for page_entry in pages:
                page_number = page_entry.get("page")
                page_text = page_entry.get("text") or ""
                page_metadata = {**common_metadata, "page": page_number}
                output.extend(
                    split_document(
                        page_text,
                        source_file=path.name,
                        source_id=f"{source_id}::page-{page_number}",
                        metadata=page_metadata,
                        chunk_size=chunk_size,
                        overlap=overlap,
                        min_chars=min_chars,
                        stats=stats,
                    )
                )
        else:
            output.extend(
                split_document(
                    report.get("full_text") or "",
                    source_file=path.name,
                    source_id=source_id,
                    metadata=common_metadata,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    min_chars=min_chars,
                    stats=stats,
                )
            )
    return output


def chunks_from_investigations(
    data_dir: Path, chunk_size: int, overlap: int, min_chars: int, stats: Counter
) -> list[dict[str, Any]]:
    path = data_dir / "investigations_metadata.json"
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return []

    investigations = load_json(path)
    output: list[dict[str, Any]] = []
    text_fields = [
        "title",
        "objective",
        "hypothesis",
        "approach",
        "research_impacts",
        "descriptors",
    ]

    for key, investigation in investigations.items():
        sections = []
        for field in text_fields:
            value = clean_component(investigation.get(field))
            if value:
                sections.append(f"{field.replace('_', ' ').title()}:\n{value}")

        publications = investigation.get("publications") or []
        for index, publication in enumerate(publications, start=1):
            title = clean_component(publication.get("title"))
            authors = clean_component(publication.get("authors"))
            doi = clean_component(publication.get("doi"))
            publication_text = "; ".join(
                part for part in [title, f"Authors: {authors}" if authors else "", f"DOI: {doi}" if doi else ""]
                if part
            )
            if publication_text:
                sections.append(f"Publication {index}: {publication_text}")

        text = "\n\n".join(sections)
        psi_id = investigation.get("psi_id") or key
        metadata = {
            "document_type": "investigation_metadata",
            "psi_id": psi_id,
            "acronym": investigation.get("acronym"),
            "title": investigation.get("title"),
            "pillar": investigation.get("pillar"),
            "research_area": investigation.get("research_area"),
        }
        output.extend(
            split_document(
                text,
                source_file=path.name,
                source_id=f"investigation-{psi_id}",
                metadata=metadata,
                chunk_size=chunk_size,
                overlap=overlap,
                min_chars=min_chars,
                stats=stats,
            )
        )
    return output


def chunks_from_experiments(data_dir: Path) -> list[dict[str, Any]]:
    """Keep each structured experiment intact as a single retrievable record.

    Experiment records are never length-filtered.
    """
    path = data_dir / "experiments_normalized.json"
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return []

    experiments = load_json(path)
    output: list[dict[str, Any]] = []
    fields = [
        "experiment_id",
        "investigation_id",
        "investigation_acronym",
        "source_test_id",
        "replicate",
        "fuel_material",
        "fuel_material_normalized",
        "fuel_phase",
        "fuel_geometry",
        "o2_concentration_pct",
        "o2_values",
        "pressure_atm",
        "pressure_values",
        "flow_velocity_cm_s",
        "flow_values",
        "flow_direction",
        "burn_time_s",
        "outcome",
        "outcome_category",
        "experiment_context",
        "gravity_level",
        "diluent",
        "flame_type",
        "is_assumed",
        "has_invalid_values",
        "condition_level",
    ]

    for index, experiment in enumerate(experiments, start=1):
        lines = []
        for field in fields:
            value = experiment.get(field)
            if value is not None and value != "" and value != []:
                lines.append(f"{field.replace('_', ' ').title()}: {clean_component(value)}")
        text = "\n".join(lines)
        exp_id = experiment.get("experiment_id") or f"row-{index}"
        metadata = {
            "document_type": "experiment_record",
            "experiment_id": exp_id,
            "psi_id": experiment.get("investigation_id"),
            "acronym": experiment.get("investigation_acronym"),
            "source_test_id": experiment.get("source_test_id"),
        }
        output.append(
            make_chunk(
                text=text,
                source_file=path.name,
                source_id=f"experiment-{exp_id}",
                chunk_index=1,
                metadata=metadata,
            )
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Recursively chunk FireOrbit processed data.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="Directory containing the processed JSON files.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output JSON file containing an array of chunks.")
    parser.add_argument("--chunk-size", type=int, default=1000,
                        help="Maximum chunk length in characters; default: 1000.")
    parser.add_argument("--overlap", type=int, default=150,
                        help="Character overlap between text chunks; default: 150.")
    parser.add_argument("--min-chunk-chars", type=int, default=DEFAULT_MIN_CHUNK_CHARS,
                        help="Drop report/investigation chunks shorter than this many "
                             "characters (page numbers, headers, bare captions); "
                             "default: 150. Use 0 to keep everything.")
    parser.add_argument("--keep-duplicates", action="store_true",
                        help="Do not remove exact duplicate report/investigation chunks.")
    args = parser.parse_args()

    if args.chunk_size < 1 or args.overlap < 0 or args.overlap >= args.chunk_size:
        parser.error("--chunk-size must be positive and --overlap must be >= 0 and smaller than --chunk-size")
    if args.min_chunk_chars < 0:
        parser.error("--min-chunk-chars must be >= 0")

    stats: Counter = Counter()
    chunks: list[dict[str, Any]] = []
    chunks.extend(chunks_from_reports(args.data_dir, args.chunk_size, args.overlap,
                                      args.min_chunk_chars, stats))
    chunks.extend(chunks_from_investigations(args.data_dir, args.chunk_size, args.overlap,
                                             args.min_chunk_chars, stats))
    chunks.extend(chunks_from_experiments(args.data_dir))

    if not args.keep_duplicates:
        chunks = remove_duplicate_chunks(chunks, stats)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(chunks, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Created {len(chunks)} chunks: {args.output}")
    print(f"Text chunking: {args.chunk_size} characters, overlap {args.overlap} characters")
    print(f"Dropped {stats['dropped_short']} short chunks (< {args.min_chunk_chars} characters)")
    print(f"Dropped {stats['dropped_duplicate']} exact duplicate chunks")
    print("Experiment rows are kept intact as one record per chunk.")


if __name__ == "__main__":
    main()