"""Embed FireOrbit chunks with BAAI/bge-base-en-v1.5 and store them in ChromaDB.

Run from the repository root:
    python embedding/embed_chunks.py                  # build / update the collection
    python embedding/embed_chunks.py --reset          # wipe the collection and rebuild
    python embedding/embed_chunks.py --query "..."    # test a search (no embedding step)

Input:  chunking/chunks.json
Output: embedding/chroma_db/  (persistent ChromaDB, collection "fireorbit_chunks")
"""

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHUNKING_DIR = PROJECT_ROOT / "chunking"
EMBEDDING_DIR = Path(__file__).resolve().parent

DEFAULT_INPUT = CHUNKING_DIR / "chunks.json"
DEFAULT_DB_PATH = EMBEDDING_DIR / "chroma_db"
DEFAULT_COLLECTION = "fireorbit_chunks"

MODEL_NAME = "BAAI/bge-base-en-v1.5"
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
MODEL_MAX_TOKENS = 512


def read_chunks(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")

    seen_ids: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise ValueError(f"Chunk at index {index} must be an object with a text string")
        chunk_id = item.get("chunk_id")
        if not chunk_id:
            raise ValueError(f"Chunk at index {index} is missing chunk_id")
        if str(chunk_id) in seen_ids:
            raise ValueError(f"Duplicate chunk_id found: {chunk_id}")
        seen_ids.add(str(chunk_id))
    return data


def flatten_metadata(metadata: Any) -> dict[str, str | int | float | bool] | None:
    """ChromaDB metadata must be flat (str/int/float/bool only).

    Nested values such as lists or dicts are stored as JSON strings, None values are dropped.
    Returns None for empty metadata because ChromaDB rejects empty dicts.
    """
    if not isinstance(metadata, dict):
        return None

    flat: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            flat[str(key)] = value
        else:
            flat[str(key)] = json.dumps(value, ensure_ascii=False)
    return flat or None


def get_collection(db_path: Path, collection_name: str, reset: bool):
    try:
        import chromadb
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency 'chromadb'. Install project requirements with: "
            "python -m pip install -r embedding/requirements.txt"
        ) from exc

    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))

    if reset:
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass  # collection did not exist

    # Embeddings are normalized, so cosine distance is the right metric.
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def load_model(max_tokens: int, device: str | None):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency 'sentence-transformers'. Install project requirements with: "
            "python -m pip install -r embedding/requirements.txt"
        ) from exc

    model = SentenceTransformer(MODEL_NAME, device=device)
    model.max_seq_length = max_tokens
    return model


def store_embeddings(
    chunks: list[dict[str, Any]],
    collection,
    batch_size: int,
    max_tokens: int,
    device: str | None,
) -> None:
    model = load_model(max_tokens, device)
    dimension = model.get_sentence_embedding_dimension()

    valid_chunks = [chunk for chunk in chunks if chunk["text"].strip()]
    skipped = len(chunks) - len(valid_chunks)
    if skipped:
        print(f"Skipping {skipped} chunks with empty text.")

    for start in range(0, len(valid_chunks), batch_size):
        batch = valid_chunks[start : start + batch_size]
        texts = [chunk["text"] for chunk in batch]
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # upsert = insert new chunks, update existing ones (safe to re-run).
        collection.upsert(
            ids=[str(chunk["chunk_id"]) for chunk in batch],
            embeddings=vectors.tolist(),
            documents=texts,
            metadatas=[flatten_metadata(chunk.get("metadata")) for chunk in batch],
        )

        completed = min(start + len(batch), len(valid_chunks))
        print(f"Embedded and stored {completed}/{len(valid_chunks)} chunks")

    print(f"Collection '{collection.name}' now holds {collection.count()} chunks.")
    print(f"Model: {MODEL_NAME} | dimensions: {dimension}")


def search(collection, query: str, top_k: int, max_tokens: int, device: str | None) -> None:
    if collection.count() == 0:
        raise SystemExit("The collection is empty. Run the script without --query first.")

    model = load_model(max_tokens, device)
    # BGE needs the instruction prefix on queries only (not on the stored passages).
    query_vector = model.encode(
        QUERY_INSTRUCTION + query,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    results = collection.query(
        query_embeddings=[query_vector.tolist()],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    for rank, (chunk_id, doc, meta, dist) in enumerate(
        zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ),
        start=1,
    ):
        print(f"\n#{rank} | id={chunk_id} | cosine distance={dist:.4f}")
        print(f"metadata: {meta}")
        print(doc[:300] + ("..." if len(doc) > 300 else ""))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed chunking/chunks.json with BAAI/bge-base-en-v1.5 and store in ChromaDB."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Input chunks JSON file (default: chunking/chunks.json).")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH,
                        help="ChromaDB persistent directory (default: embedding/chroma_db).")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION,
                        help=f"ChromaDB collection name (default: {DEFAULT_COLLECTION}).")
    parser.add_argument("--reset", action="store_true",
                        help="Delete the collection before rebuilding it.")
    parser.add_argument("--query", default=None,
                        help="Run a test search against the existing collection and exit.")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Number of results for --query (default: 5).")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Number of chunks to encode per batch (default: 32).")
    parser.add_argument("--max-tokens", type=int, default=MODEL_MAX_TOKENS,
                        help="Maximum model input length in tokens, up to 512 (default: 512).")
    parser.add_argument("--device", default=None,
                        help="Optional device, for example cpu, cuda, or cuda:0. Auto-selected by default.")
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if args.max_tokens < 1 or args.max_tokens > MODEL_MAX_TOKENS:
        parser.error(f"--max-tokens must be between 1 and {MODEL_MAX_TOKENS} for this model")

    collection = get_collection(args.db_path, args.collection, reset=args.reset)

    if args.query:
        search(collection, args.query, args.top_k, args.max_tokens, args.device)
        return

    if not args.input.is_file():
        parser.error(f"Input file not found: {args.input}")

    chunks = read_chunks(args.input)
    store_embeddings(
        chunks=chunks,
        collection=collection,
        batch_size=args.batch_size,
        max_tokens=args.max_tokens,
        device=args.device,
    )


if __name__ == "__main__":
    main()
