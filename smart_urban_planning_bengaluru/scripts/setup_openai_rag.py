"""Create an OpenAI vector store and upload the Bengaluru planning PDF.

Usage (from the project root):
    python scripts\\setup_openai_rag.py

The script reads OPENAI_API_KEY from .env, uploads the selected planning
PDF to the OpenAI File API, creates a vector store, waits for ingestion,
and writes OPENAI_VECTOR_STORE_ID into .env.
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'data' / 'documents' / 'RMP_2031_Volume_1_Vision_Document_Draft.pdf'
ENV = ROOT / '.env'
ENV_EXAMPLE = ROOT / '.env.example'

try:
    from dotenv import load_dotenv
    load_dotenv(ENV)
except Exception:
    pass

api_key = os.getenv('OPENAI_API_KEY', '').strip()
if not api_key:
    print('ERROR: OPENAI_API_KEY is not set in .env')
    print('Create .env from .env.example, add your key, then rerun this script.')
    sys.exit(1)

if not DOC.exists():
    print(f'ERROR: planning PDF not found: {DOC}')
    sys.exit(1)

try:
    from openai import OpenAI
except Exception as exc:
    print('ERROR: OpenAI Python SDK is not installed.')
    print('Run: python -m pip install -r requirements.txt')
    print(exc)
    sys.exit(1)

client = OpenAI(api_key=api_key)
print(f'Uploading: {DOC.name}')

vector_store_id = os.getenv('OPENAI_VECTOR_STORE_ID', '').strip()
if vector_store_id:
    print(f'Existing vector store configured: {vector_store_id}')
    print('To create a fresh store, remove OPENAI_VECTOR_STORE_ID from .env and rerun.')
    sys.exit(0)

store = client.vector_stores.create(name='Bengaluru Urban Planning Knowledge Base')
print(f'Created vector store: {store.id}')

with DOC.open('rb') as f:
    result = client.vector_stores.files.upload_and_poll(store.id, file=f)

print(f'Ingestion status: {result.status}')
if getattr(result, 'status', '') != 'completed':
    print(f'ERROR: vector-store ingestion did not complete: {result}')
    sys.exit(1)

# Update/create .env without overwriting unrelated settings.
lines = ENV.read_text(encoding='utf-8').splitlines() if ENV.exists() else ENV_EXAMPLE.read_text(encoding='utf-8').splitlines()
updated = []
found = False
for line in lines:
    if line.startswith('OPENAI_VECTOR_STORE_ID='):
        updated.append(f'OPENAI_VECTOR_STORE_ID={store.id}')
        found = True
    else:
        updated.append(line)
if not found:
    updated.append(f'OPENAI_VECTOR_STORE_ID={store.id}')
if not any(line.startswith('LLM_PROVIDER=') for line in updated):
    updated.append('LLM_PROVIDER=openai')
else:
    updated = [
        ('LLM_PROVIDER=openai' if line.startswith('LLM_PROVIDER=') else line)
        for line in updated
    ]

ENV.write_text('\n'.join(updated) + '\n', encoding='utf-8')
print(f'Saved vector store ID to: {ENV}')
print('Next: restart the FastAPI server and call /rag/status.')
