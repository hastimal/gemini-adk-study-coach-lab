"""Google ADK tools for document search, retrieval, and grounding verification."""

from typing import Any

from study_coach.rag.index import document_index_registry


def search_uploaded_documents(
    query: str, session_id: str, top_k: int = 4
) -> dict[str, Any]:
    """Searches uploaded study guide documents in the active session for relevant passages.

    Args:
        query: Technical search term or question to find in documents.
        session_id: Active session ID to ensure session-isolated retrieval.
        top_k: Number of relevant passages to retrieve (default: 4).

    Returns:
        Dictionary with list of retrieved chunks, page numbers, and snippet citations.
    """
    index = document_index_registry.get_index(session_id)
    if not index or not index.chunks:
        return {
            "query": query,
            "session_id": session_id,
            "found": False,
            "chunks": [],
            "message": "No documents uploaded or indexed in this session. Ask the student to upload a guide first.",
        }

    scored_chunks = index.search(query=query, top_k=top_k)
    if not scored_chunks:
        return {
            "query": query,
            "session_id": session_id,
            "found": False,
            "chunks": [],
            "message": "No matching passages found in the uploaded documents for this query.",
        }

    results = []
    for chunk, score in scored_chunks:
        results.append(
            {
                "chunk_id": chunk.chunk_id,
                "doc_name": chunk.doc_name,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": round(score, 3),
            }
        )

    return {
        "query": query,
        "session_id": session_id,
        "found": True,
        "match_count": len(results),
        "chunks": results,
    }


def list_session_documents(session_id: str) -> dict[str, Any]:
    """Lists all uploaded documents available in the active session index."""
    index = document_index_registry.get_index(session_id)
    if not index or not index.documents:
        return {"session_id": session_id, "document_count": 0, "documents": []}

    docs = [
        {
            "doc_id": d.doc_id,
            "filename": d.filename,
            "file_type": d.file_type,
            "total_pages": d.total_pages,
            "total_chunks": d.total_chunks,
        }
        for d in index.list_documents()
    ]
    return {"session_id": session_id, "document_count": len(docs), "documents": docs}
