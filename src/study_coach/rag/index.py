"""In-memory, session-isolated document retriever for Google ADK Study Coach.

Provides lightweight, deterministic TF-IDF / BM25-style lexical scoring and token-overlap
matching. Zero mandatory external databases or paid vector services, fully reproducible
for local workshops and offline CI/CD test runs.
"""

import math
import re
from collections import Counter

from study_coach.models.document import (
    DocumentChunk,
    DocumentCitation,
    DocumentMetadata,
)


class LocalDocumentIndex:
    """In-memory document index for a single learning session."""

    def __init__(self, session_id: str) -> None:
        self.session_id: str = session_id
        self.documents: dict[str, DocumentMetadata] = {}
        self.chunks: list[DocumentChunk] = []
        self._doc_frequencies: Counter[str] = Counter()
        self._total_chunks: int = 0

    def add_document(
        self, metadata: DocumentMetadata, chunks: list[DocumentChunk]
    ) -> None:
        """Adds a document and its chunks into the session index."""
        # Replace if existing
        if metadata.doc_id in self.documents:
            self.remove_document(metadata.doc_id)

        self.documents[metadata.doc_id] = metadata
        self.chunks.extend(chunks)
        self._rebuild_index()

    def remove_document(self, doc_id: str) -> bool:
        """Removes a document and its chunks from the session index."""
        if doc_id not in self.documents:
            return False
        del self.documents[doc_id]
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]
        self._rebuild_index()
        return True

    def clear(self) -> None:
        """Clears all indexed documents and chunks for this session."""
        self.documents.clear()
        self.chunks.clear()
        self._doc_frequencies.clear()
        self._total_chunks = 0

    def get_document(self, doc_id: str) -> DocumentMetadata | None:
        return self.documents.get(doc_id)

    def list_documents(self) -> list[DocumentMetadata]:
        return list(self.documents.values())

    def search(
        self,
        query: str,
        top_k: int = 4,
        min_score: float = 0.05,
        target_doc_id: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Performs BM25-inspired keyword retrieval over indexed chunks."""
        if not self.chunks or not query.strip():
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored_chunks: list[tuple[DocumentChunk, float]] = []
        candidate_chunks = (
            [c for c in self.chunks if c.doc_id == target_doc_id]
            if target_doc_id
            else self.chunks
        )

        avg_chunk_len = (
            sum(len(_tokenize(c.content)) for c in candidate_chunks)
            / len(candidate_chunks)
            if candidate_chunks
            else 1.0
        )
        k1 = 1.2
        b = 0.75

        for chunk in candidate_chunks:
            chunk_tokens = _tokenize(chunk.content)
            chunk_len = len(chunk_tokens)
            if chunk_len == 0:
                continue

            term_counts = Counter(chunk_tokens)
            score = 0.0

            for q_term in query_tokens:
                if q_term not in term_counts:
                    continue

                tf = term_counts[q_term]
                df = self._doc_frequencies.get(q_term, 1)
                idf = math.log(1.0 + (self._total_chunks - df + 0.5) / (df + 0.5))
                denom = tf + k1 * (1.0 - b + b * (chunk_len / avg_chunk_len))
                score += idf * ((tf * (k1 + 1.0)) / denom)

            # Extra weight for exact match of query phrases
            clean_q = query.lower().strip()
            if len(clean_q) > 4 and clean_q in chunk.content.lower():
                score += 2.0

            if score >= min_score:
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

    def build_citations(
        self, scored_chunks: list[tuple[DocumentChunk, float]]
    ) -> list[DocumentCitation]:
        """Creates verifiable DocumentCitation models from retrieved chunks."""
        citations: list[DocumentCitation] = []
        for chunk, _ in scored_chunks:
            snippet = chunk.content[:250].replace("\n", " ").strip()
            if len(chunk.content) > 250:
                snippet += "..."
            citations.append(
                DocumentCitation(
                    doc_id=chunk.doc_id,
                    doc_name=chunk.doc_name,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    snippet=snippet,
                )
            )
        return citations

    def _rebuild_index(self) -> None:
        """Recomputes document frequencies across all active chunks."""
        self._doc_frequencies.clear()
        self._total_chunks = len(self.chunks)
        for chunk in self.chunks:
            unique_terms = set(_tokenize(chunk.content))
            for term in unique_terms:
                self._doc_frequencies[term] += 1


class DocumentIndexRegistry:
    """Manages session-isolated local document indexes in memory."""

    def __init__(self) -> None:
        self._indexes: dict[str, LocalDocumentIndex] = {}

    def get_or_create(self, session_id: str) -> LocalDocumentIndex:
        if session_id not in self._indexes:
            self._indexes[session_id] = LocalDocumentIndex(session_id=session_id)
        return self._indexes[session_id]

    def remove_session(self, session_id: str) -> None:
        if session_id in self._indexes:
            self._indexes[session_id].clear()
            del self._indexes[session_id]

    def get_index(self, session_id: str) -> LocalDocumentIndex | None:
        return self._indexes.get(session_id)


# Global process-level registry for active student sessions
document_index_registry = DocumentIndexRegistry()


_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "from",
    "of",
    "is",
    "are",
    "was",
    "were",
    "what",
    "how",
    "why",
    "which",
    "who",
    "when",
    "where",
    "this",
    "that",
    "these",
    "those",
    "can",
    "does",
    "do",
    "explain",
    "describe",
    "tell",
    "me",
    "about",
}


def _tokenize(text: str) -> list[str]:
    """Tokenizes string into normalized words, filtering short stopwords."""
    words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
    return [w for w in words if w not in _STOPWORDS]
