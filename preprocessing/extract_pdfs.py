import os
import re
import json
from pathlib import Path
import fitz # PyMuPDF
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = PROJECT_ROOT / "DATA" / "nasa final data"
OUTPUT_DIR = PROJECT_ROOT / "data_processed"

def extract_pdf_data(pdf_path):
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    text_chunks = []
    
    # We extract full text and maintain page mapping, keeping text clean and concise
    for page_num in range(total_pages):
        page = doc[page_num]
        txt = page.get_text("text")
        if txt.strip():
            text_chunks.append({
                "page": page_num + 1,
                "text": txt.strip()
            })
            
    full_text = "\n\n".join([c["text"] for c in text_chunks])
    
    # Simple regex to locate key sections if present
    sections = {}
    for heading in ["abstract", "introduction", "objective", "results", "conclusions", "summary", "recommendations"]:
        m = re.search(rf"(?i)\b({heading})\b[:\n\r]+(.*?)(?=\n[A-Z0-9\s]{{3,25}}\b|\Z)", full_text, re.DOTALL)
        if m:
            sections[heading] = m.group(2)[:2000].strip()

    return {
        "filename": Path(pdf_path).name,
        "total_pages": total_pages,
        "sections": sections,
        "text_preview": full_text[:4000],
        "full_text_length": len(full_text)
    }

def main():
    base_dir = BASE_DIR
    out_file = OUTPUT_DIR / "extracted_pdf_reports.json"
    
    pdf_results = {}
    
    for pdf_path in base_dir.rglob("*.pdf"):
        parent_folder = pdf_path.parent.name
        # Skip small/temp or deeply nested duplicates if any
        print(f"Processing PDF: {pdf_path.name} in {parent_folder}...")
        try:
            data = extract_pdf_data(pdf_path)
            key = f"{parent_folder}/{pdf_path.name}"
            pdf_results[key] = data
        except Exception as e:
            print(f"Error reading {pdf_path.name}: {e}")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(pdf_results, f, indent=2, ensure_ascii=False)
        
    print(f"\nExtracted text from {len(pdf_results)} PDFs into: {out_file}")

if __name__ == "__main__":
    main()

