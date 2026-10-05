from pathlib import Path
import re
from typing import List, Dict, Any

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer

from .settings import (
    RAG_DIR,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_VECTOR_STORE_ID,
)


class LocalRAG:
    """Local TF-IDF RAG fallback. Useful when no hosted OpenAI vector store is configured."""

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.vectorizer = None
        self.matrix = None
        self.documents: List[str] = []
        self._build()

    def _chunk(self, text: str, size: int = 1400, overlap: int = 200):
        text = re.sub(r'\s+', ' ', text).strip()
        chunks = []
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            piece = text[start:end].strip()
            if piece:
                chunks.append(piece)
            if end == len(text):
                break
            start = max(0, end - overlap)
        return chunks

    def _read_file(self, path: Path):
        suffix = path.suffix.lower()
        if suffix == '.pdf':
            reader = PdfReader(str(path))
            for page_no, page in enumerate(reader.pages, start=1):
                yield page_no, page.extract_text() or ''
        elif suffix in {'.txt', '.md'}:
            yield None, path.read_text(encoding='utf-8', errors='ignore')

    def _build(self):
        self.chunks = []
        self.documents = []
        self.vectorizer = None
        self.matrix = None
        RAG_DIR.mkdir(parents=True, exist_ok=True)

        for path in sorted(RAG_DIR.iterdir()):
            if path.name.lower() in {'readme.md', 'sources.md'} or path.suffix.lower() not in {'.pdf', '.txt', '.md'}:
                continue
            try:
                added = False
                for page_no, text in self._read_file(path):
                    chunks = self._chunk(text)
                    for idx, chunk in enumerate(chunks):
                        self.chunks.append({
                            'document': path.name,
                            'page': page_no,
                            'chunk': idx,
                            'text': chunk,
                            'source': str(path),
                        })
                        added = True
                if added:
                    self.documents.append(path.name)
            except Exception as exc:
                self.chunks.append({
                    'document': path.name,
                    'page': None,
                    'chunk': None,
                    'text': f'ERROR_READING_DOCUMENT: {exc}',
                    'source': str(path),
                    'error': True,
                })

        usable = [c for c in self.chunks if not c.get('error') and c.get('text')]
        if usable:
            self.vectorizer = TfidfVectorizer(
                stop_words='english',
                ngram_range=(1, 2),
                max_features=50000,
            )
            self.matrix = self.vectorizer.fit_transform([c['text'] for c in usable])
            self.chunks = usable

    def reload(self):
        self._build()
        return self.status()

    def status(self):
        return {
            'provider': 'local',
            'status': 'ready' if self.chunks else 'knowledge_base_empty',
            'document_count': len(self.documents),
            'documents': self.documents,
            'chunk_count': len(self.chunks),
            'directory': str(RAG_DIR),
        }

    def search(self, query: str, top_k: int = 5):
        if not self.chunks or self.vectorizer is None or self.matrix is None:
            return {
                'provider': 'local',
                'status': 'knowledge_base_empty',
                'results': [],
                'document_count': len(self.documents),
            }
        q = self.vectorizer.transform([query or ''])
        scores = (self.matrix @ q.T).toarray().ravel()
        idxs = scores.argsort()[::-1][:max(1, top_k)]
        results = []
        for i in idxs:
            if scores[i] <= 0:
                continue
            item = dict(self.chunks[i])
            item['relevance_score'] = round(float(scores[i]), 4)
            results.append(item)
        return {
            'provider': 'local',
            'status': 'ok' if results else 'no_relevant_rule_found',
            'results': results,
            'document_count': len(self.documents),
        }


class OpenAIRAG:
    """OpenAI-hosted vector-store/file-search RAG."""

    def __init__(self):
        self.client = None
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=OPENAI_API_KEY)
            except Exception as exc:
                self._init_error = str(exc)
            else:
                self._init_error = None
        else:
            self._init_error = 'OPENAI_API_KEY is not configured.'

    @property
    def configured(self) -> bool:
        return bool(self.client and OPENAI_VECTOR_STORE_ID)

    def status(self):
        if not OPENAI_API_KEY:
            return {
                'provider': 'openai',
                'status': 'not_configured',
                'reason': 'OPENAI_API_KEY is not configured.',
                'vector_store_id': OPENAI_VECTOR_STORE_ID or None,
            }
        if not OPENAI_VECTOR_STORE_ID:
            return {
                'provider': 'openai',
                'status': 'not_configured',
                'reason': 'OPENAI_VECTOR_STORE_ID is not configured.',
                'vector_store_id': None,
            }
        if self.client is None:
            return {
                'provider': 'openai',
                'status': 'error',
                'reason': self._init_error or 'OpenAI client could not be initialized.',
                'vector_store_id': OPENAI_VECTOR_STORE_ID,
            }
        return {
            'provider': 'openai',
            'status': 'ready',
            'vector_store_id': OPENAI_VECTOR_STORE_ID,
            'model': OPENAI_MODEL,
        }

    def search(self, query: str, top_k: int = 5, scenario: Dict[str, Any] | None = None):
        if not self.configured:
            return self.status() | {'results': []}

        scenario = scenario or {}
        scenario_text = self._scenario_query(query, scenario)
        try:
            response = self.client.responses.create(
                model=OPENAI_MODEL,
                input=(
                    'You are a planning-research retrieval assistant. '
                    'Use ONLY the retrieved passages from the Bengaluru planning documents. '
                    'Do not invent rules. Distinguish draft policy discussion from legally binding requirements. '
                    'Return concise evidence items with document and page when available.\n\n'
                    f'Scenario/query:\n{scenario_text}'
                ),
                tools=[{
                    'type': 'file_search',
                    'vector_store_ids': [OPENAI_VECTOR_STORE_ID],
                    'max_num_results': max(1, min(int(top_k), 20)),
                }],
                include=['file_search_call.results'],
            )

            raw = response.model_dump() if hasattr(response, 'model_dump') else {}
            results = self._extract_results(raw)
            answer = getattr(response, 'output_text', '') or ''
            return {
                'provider': 'openai',
                'status': 'ok' if results or answer else 'no_relevant_rule_found',
                'results': results,
                'answer': answer,
                'document_count': len({r.get('document') for r in results if r.get('document')}),
                'vector_store_id': OPENAI_VECTOR_STORE_ID,
            }
        except Exception as exc:
            return {
                'provider': 'openai',
                'status': 'error',
                'reason': str(exc),
                'results': [],
                'document_count': 0,
                'vector_store_id': OPENAI_VECTOR_STORE_ID,
            }

    def _scenario_query(self, query: str, scenario: Dict[str, Any]):
        development = scenario.get('development') or {}
        location = scenario.get('location') or {}
        findings = scenario.get('spatial_findings') or {}
        keywords = [
            development.get('type'),
            'land use', 'zoning', 'residential development',
            'transportation', 'social infrastructure',
            'environment', 'water bodies', 'green areas',
            'mixed land use', 'density', 'planning regulations',
        ]
        nearby = ', '.join(
            f"{k}: {v.get('count_within_radius')} within radius"
            for k, v in findings.items()
            if isinstance(v, dict) and 'count_within_radius' in v
        )
        return (
            f"{query}\n"
            f"Location: {location.get('latitude')}, {location.get('longitude')}\n"
            f"Development: {development.get('type')}\n"
            f"Units: {development.get('units')}\n"
            f"Nearby context: {nearby}\n"
            f"Relevant planning topics: {', '.join(x for x in keywords if x)}"
        )

    @staticmethod
    def _extract_results(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for item in raw.get('output', []) or []:
            if item.get('type') != 'file_search_call':
                continue
            for result in item.get('results', []) or []:
                content = result.get('content') or []
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        text_parts.append(part.get('text', ''))
                results.append({
                    'document': result.get('filename') or result.get('file_id'),
                    'file_id': result.get('file_id'),
                    'relevance_score': result.get('score'),
                    'text': '\n'.join(x for x in text_parts if x).strip(),
                })
        return results


local_rag = LocalRAG()
openai_rag = OpenAIRAG()


def _provider():
    return openai_rag if LLM_PROVIDER == 'openai' else local_rag


class RAGFacade:
    def status(self):
        result = _provider().status()
        result['configured_provider'] = LLM_PROVIDER
        result['fallback_local_status'] = local_rag.status()
        return result

    def reload(self):
        local_status = local_rag.reload()
        if LLM_PROVIDER == 'openai':
            return openai_rag.status() | {'fallback_local_status': local_status}
        return local_status

    def search(self, query: str, top_k: int = 5, scenario: Dict[str, Any] | None = None):
        if LLM_PROVIDER == 'openai':
            result = openai_rag.search(query, top_k, scenario)
            # If OpenAI is not configured, retain a useful local fallback rather than claiming KB is empty.
            if result.get('status') in {'not_configured', 'error'} and local_rag.chunks:
                fallback = local_rag.search(query, top_k)
                fallback['fallback_reason'] = result.get('reason') or result.get('status')
                fallback['openai_status'] = result
                return fallback
            return result
        return local_rag.search(query, top_k)


rag = RAGFacade()
