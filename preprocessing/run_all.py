import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "parse_isatab.py",
    "normalize_csv.py",
    "extract_pdfs.py",
    "chunk_reports.py",
    "build_knowledge_base.py",
]


def main():
    here = Path(__file__).resolve().parent
    for name in SCRIPTS:
        path = here / name
        print(f"\n=== Running {name} ===")
        subprocess.check_call([sys.executable, str(path)])


if __name__ == "__main__":
    main()
