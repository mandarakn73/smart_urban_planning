"""Prepare verified planning documents for the local RAG index.

Usage:
    python scripts/ingest_documents.py path/to/rule.pdf path/to/other.pdf
"""
from pathlib import Path
import shutil
import sys

ALLOWED={'.pdf','.txt','.md'}

def main():
    target=Path('data/documents'); target.mkdir(parents=True,exist_ok=True)
    sources=[Path(x) for x in sys.argv[1:]]
    if not sources:
        print('No input documents supplied.')
        print('Place verified planning PDFs in data/documents or pass file paths to this script.')
        return
    for src in sources:
        if not src.exists():
            print(f'SKIP missing: {src}')
            continue
        if src.suffix.lower() not in ALLOWED:
            print(f'SKIP unsupported type: {src}')
            continue
        dest=target/src.name
        if src.resolve()!=dest.resolve():
            shutil.copy2(src,dest)
            print(f'COPIED {src} -> {dest}')
        else:
            print(f'ALREADY IN KB {dest}')
    print('Documents now available for RAG:')
    for p in sorted(target.iterdir()):
        if p.suffix.lower() in ALLOWED:
            print(' -',p.name)

if __name__=='__main__': main()
