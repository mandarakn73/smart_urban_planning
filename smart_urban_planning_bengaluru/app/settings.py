import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

APP_HOST = os.getenv('APP_HOST', '127.0.0.1')
APP_PORT = int(os.getenv('APP_PORT', '8000'))
DATA_GPKG = ROOT / os.getenv('DATA_GPKG', 'data/processed/bengaluru_urban.gpkg')
TRAFFIC_FILE = ROOT / os.getenv('TRAFFIC_FILE', 'data/raw/bengaluru_traffic_events.csv')
RAG_DIR = ROOT / os.getenv('RAG_DIR', 'data/documents')
DEFAULT_RADIUS_M = float(os.getenv('DEFAULT_RADIUS_M', '500'))
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'none').lower()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
OPENAI_VECTOR_STORE_ID = os.getenv('OPENAI_VECTOR_STORE_ID', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-3-7-sonnet-latest')
