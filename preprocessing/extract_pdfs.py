import re
from pathlib import Path

import fitz

from utils import BASE_DIR, OUTPUT_DIR, dump_json, ensure_output_dir, psi_id_from_folder

HEADING_RE = re.compile(
    r"(?im)^\s*(abstract|introduction|objective[s]?|results?|conclusions?|summary|recommendations?)\s*:?\s*$"
)


def extract_pdf_data(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        txt = doc[page_num].get_text("text")
        if txt and txt.strip():
            pages.append({"page": page_num + 1, "text": txt.strip()})
    full_text = "\n\n".join(p["text"] for p in pages)
    sections = {}
    matches = list(HEADING_RE.finditer(full_text))
    for i, m in enumerate(matches):
        heading = m.group(1).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(full_text), start + 4000)
        body = full_text[start:end].strip()
        if body and heading not in sections:
            sections[heading] = body[:3000]
    return {
        "filename": Path(pdf_path).name,
        "total_pages": len(doc),
        "sections": sections,
        "pages": pages,
        "full_text": full_text,
        "full_text_length": len(full_text),
        "text_preview": full_text[:4000],
    }


def extract_doc_text(doc_path):
    try:
        import win32com.client
    except ImportError:
        return None
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        document = word.Documents.Open(str(doc_path))
        text = document.Content.Text
        document.Close(False)
        return text
    except Exception as exc:
        print(f"Could not extract {doc_path.name}: {exc}")
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


def main():
    ensure_output_dir()
    pdf_results = {}
    base_dir = BASE_DIR

    for pdf_path in sorted(base_dir.rglob("*.pdf")):
        rel = pdf_path.relative_to(base_dir).as_posix()
        folder = pdf_path.relative_to(base_dir).parts[0] if pdf_path.parent != base_dir else None
        psi_id = psi_id_from_folder(folder) if folder and pdf_path.parent != base_dir else None
        if folder and folder.lower().endswith(".pdf"):
            folder = None
            psi_id = None
        print(f"Processing PDF: {rel}")
        try:
            data = extract_pdf_data(pdf_path)
            data.update({
                "relative_path": rel,
                "investigation_folder": folder,
                "psi_id": psi_id,
                "source_type": "global_guide" if psi_id is None else "investigation_report",
            })
            pdf_results[rel] = data
        except Exception as e:
            print(f"Error reading {rel}: {e}")

    for doc_path in sorted(base_dir.rglob("*.doc")):
        if doc_path.suffix.lower() == ".docx":
            continue
        rel = doc_path.relative_to(base_dir).as_posix()
        folder = doc_path.relative_to(base_dir).parts[0]
        psi_id = psi_id_from_folder(folder)
        print(f"Processing DOC: {rel}")
        text = extract_doc_text(doc_path)
        if not text:
            pdf_results[rel] = {
                "filename": doc_path.name,
                "relative_path": rel,
                "investigation_folder": folder,
                "psi_id": psi_id,
                "source_type": "investigation_report",
                "total_pages": None,
                "sections": {},
                "pages": [],
                "full_text": "",
                "full_text_length": 0,
                "text_preview": "",
                "extraction_error": "legacy .doc not extracted (Word/win32com unavailable)",
            }
            continue
        pdf_results[rel] = {
            "filename": doc_path.name,
            "relative_path": rel,
            "investigation_folder": folder,
            "psi_id": psi_id,
            "source_type": "investigation_report",
            "total_pages": None,
            "sections": {},
            "pages": [{"page": 1, "text": text.strip()}],
            "full_text": text.strip(),
            "full_text_length": len(text.strip()),
            "text_preview": text.strip()[:4000],
        }

    out_file = OUTPUT_DIR / "extracted_pdf_reports.json"
    dump_json(out_file, pdf_results)
    print(f"\nExtracted {len(pdf_results)} documents into: {out_file}")


if __name__ == "__main__":
    main()
