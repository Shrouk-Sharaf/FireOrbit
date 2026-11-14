"""Build a persistent ChromaDB vector index from FireOrbit's chunks.json.

Setup:
    pip install chromadb sentence-transformers

Build the index (from the repository root):
    python embedding/build_index.py

Test a query:
    python embedding/build_index.py --query "What happens to flame spread at low oxygen?"
    python embedding/build_index.py --query "burn time of cotton" --doc-type experiment_record
"""

import argparse
import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS = PROJECT_ROOT / "chunking" / "chunks.json"
DEFAULT_DB_DIR = PROJECT_ROOT / "index" / "chroma"
COLLECTION = "fireorbit"

# Some embedding models expect a prefix on documents and on queries.
PREFIXES = {
    "intfloat/multilingual-e5-base": ("passage: ", "query: "),
    "intfloat/multilingual-e5-small": ("passage: ", "query: "),
    "BAAI/bge-small-en-v1.5": ("", "Represent this sentence for searching relevant passages: "),
    "BAAI/bge-base-en-v1.5": ("", "Represent this sentence for searching relevant passages: "),
}


def prefixes(model_name: str) -> tuple[str, str]:
    return PREFIXES.get(model_name, ("", ""))


def clean_metadata(metadata: dict) -> dict:
    """Chroma only accepts str/int/float/bool values, so drop None and flatten the rest."""
    out = {}
    for key, value in metadata.items():
        if value is None:
            continue
        out[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
    return out


def load_chunks(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        chunks = json.load(handle)
    print(f"Loaded {len(chunks)} chunks")
    return chunks


def build(args) -> None:
    chunks = load_chunks(args.chunks)
    model = SentenceTransformer(args.model)
    doc_prefix, _ = prefixes(args.model)

    client = chromadb.PersistentClient(path=str(args.db_dir))
    # Rebuild from scratch so the index always matches chunks.json.
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    for start in range(0, len(chunks), args.batch_size):
        batch = chunks[start : start + args.batch_size]
        texts = [doc_prefix + c["text"] for c in batch]
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        collection.add(
            ids=[c["chunk_id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=embeddings.tolist(),
            metadatas=[clean_metadata(c["metadata"]) for c in batch],
        )
        print(f"Indexed {min(start + args.batch_size, len(chunks))}/{len(chunks)}")

    print(f"Done. {collection.count()} chunks stored in {args.db_dir}")


def query(args) -> None:
    client = chromadb.PersistentClient(path=str(args.db_dir))
    collection = client.get_collection(COLLECTION)
    model = SentenceTransformer(args.model)
    _, query_prefix = prefixes(args.model)

    where = {"document_type": args.doc_type} if args.doc_type else None
    embedding = model.encode([query_prefix + args.query], normalize_embeddings=True)
    results = collection.query(
        query_embeddings=embedding.tolist(), n_results=args.top_k, where=where
    )

    for rank, (cid, doc, meta, dist) in enumerate(
        zip(results["ids"][0], results["documents"][0],
            results["metadatas"][0], results["distances"][0]), start=1):
        print(f"\n#{rank}  score={1 - dist:.3f}  {cid}")
        print(f"    type={meta.get('document_type')}  psi_id={meta.get('psi_id')}  page={meta.get('page')}")
        print("    " + doc[:300].replace("\n", " "))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build / query the FireOrbit vector index.")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5",
                        help="Sentence-transformers model. For Arabic questions use "
                             "intfloat/multilingual-e5-base.")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--query", help="If given, search the existing index instead of building.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--doc-type", choices=["report", "experiment_record", "investigation_metadata"],
                        help="Optional metadata filter for --query.")
    args = parser.parse_args()

    query(args) if args.query else build(args)


if __name__ == "__main__":
    main()
