"""Domain models for Document AI, chunking, citations, and conversation history."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentCitation(BaseModel):
    """Citation linking an answer or explanation back to an exact source document location."""

    doc_id: str = Field(..., description="Document identifier")
    doc_name: str = Field(..., description="Original filename of the document")
    page_number: int | None = Field(
        default=None, description="1-based page number where the evidence appears"
    )
    section_title: str | None = Field(
        default=None, description="Section heading or title if available"
    )
    snippet: str = Field(
        ...,
        max_length=600,
        description="Verifiable excerpt or snippet text supporting the answer",
    )


class DocumentChunk(BaseModel):
    """Chunk of text extracted from a parsed document with provenance metadata."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    doc_id: str = Field(..., description="Document identifier this chunk belongs to")
    doc_name: str = Field(..., description="Original filename")
    page_number: int | None = Field(
        default=None, description="1-based page number for PDF/paginated documents"
    )
    section_title: str | None = Field(
        default=None, description="Section title or paragraph heading"
    )
    content: str = Field(..., description="Extracted clean text content")
    chunk_index: int = Field(default=0, ge=0, description="Sequential index of chunk")
    token_count_approx: int = Field(default=0, ge=0)


class DocumentMetadata(BaseModel):
    """Metadata describing an uploaded study guide or document."""

    doc_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    file_type: Literal["pdf", "docx", "txt", "md"] = Field(
        ..., description="Supported file extension"
    )
    file_size_bytes: int = Field(..., gt=0, description="Size of file in bytes")
    total_pages: int | None = Field(
        default=None, description="Total pages if PDF/paginated"
    )
    total_chunks: int = Field(default=0, ge=0, description="Total extracted chunks")
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Upload timestamp",
    )
    char_count: int = Field(default=0, ge=0)


class DocumentGroundingResult(BaseModel):
    """Structured response from the Document AI Agent."""

    query: str = Field(..., description="Student's technical or document query")
    answer: str = Field(..., description="Comprehensive, source-grounded response")
    is_grounded_in_doc: bool = Field(
        ...,
        description="True if answered from uploaded documents; False if unsupported or general knowledge",
    )
    citations: list[DocumentCitation] = Field(
        default_factory=list,
        description="Exact source citations supporting the answer",
    )
    follow_up_suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions to deepen understanding",
    )
    unsupported_reason: str | None = Field(
        default=None,
        description="Explanation if the query cannot be answered from the uploaded document",
    )


class ChatMessage(BaseModel):
    """Multi-turn conversation message in the Study Coach chat session."""

    role: Literal["student", "coach", "system"] = Field(
        ..., description="Role of the message sender"
    )
    content: str = Field(..., description="Message text or markdown")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_routed: str | None = Field(
        default=None,
        description="Agent that produced this response (e.g. topic_expert, document_agent, quiz_generator)",
    )
    citations: list[DocumentCitation] = Field(
        default_factory=list,
        description="Source citations if the message is document-grounded",
    )
    quiz_id: str | None = Field(
        default=None,
        description="Associated quiz ID if this message contains a quiz",
    )
    follow_up_prompt: str | None = Field(
        default=None,
        description="Interactive follow-up question asked by the Coach",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary message metadata"
    )
