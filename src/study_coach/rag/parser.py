"""Document parser for PDF, DOCX, TXT, and Markdown files.

Extracts text, preserves page and section provenance, enforces size limits,
and generates cleanly bounded chunks with metadata.
"""

import io
import logging
import re
import uuid
from typing import BinaryIO

import docx
from pypdf import PdfReader

from study_coach.models.document import DocumentChunk, DocumentMetadata

logger = logging.getLogger(__name__)

# Workshop limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_DOCS = 10
CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


class DocumentParseError(Exception):
    """Raised when an uploaded document cannot be parsed or validated."""


def validate_upload(filename: str, file_bytes: bytes) -> tuple[str, str]:
    """Validates filename extension and size limits. Returns (doc_id, extension)."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise DocumentParseError(
            f"File '{filename}' exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."
        )

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx", "txt", "md"):
        raise DocumentParseError(
            f"Unsupported file format '.{ext}'. Supported formats are: PDF, DOCX, TXT, MD."
        )

    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    return doc_id, ext


def parse_pdf(
    file_stream: BinaryIO, doc_id: str, filename: str
) -> tuple[DocumentMetadata, list[DocumentChunk]]:
    """Extracts text from PDF, recording page numbers and creating chunks."""
    try:
        reader = PdfReader(file_stream)
        total_pages = len(reader.pages)
        chunks: list[DocumentChunk] = []
        total_chars = 0
        chunk_idx = 0

        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = _clean_text(text)
            if not text:
                continue

            total_chars += len(text)
            # Create chunks per page to preserve page citations accurately
            page_chunks = _chunk_text(
                text=text,
                doc_id=doc_id,
                doc_name=filename,
                page_number=page_idx,
                section_title=f"Page {page_idx}",
                start_index=chunk_idx,
            )
            chunks.extend(page_chunks)
            chunk_idx += len(page_chunks)

        metadata = DocumentMetadata(
            doc_id=doc_id,
            filename=filename,
            file_type="pdf",
            file_size_bytes=file_stream.seek(0, io.SEEK_END) or 0,
            total_pages=total_pages,
            total_chunks=len(chunks),
            char_count=total_chars,
        )
        return metadata, chunks
    except Exception as exc:
        if isinstance(exc, DocumentParseError):
            raise
        raise DocumentParseError(f"Failed to parse PDF '{filename}': {exc}") from exc


def parse_docx(
    file_stream: BinaryIO, doc_id: str, filename: str
) -> tuple[DocumentMetadata, list[DocumentChunk]]:
    """Extracts text from DOCX, tracking headings and section titles."""
    try:
        doc = docx.Document(file_stream)
        chunks: list[DocumentChunk] = []
        current_section = "Introduction"
        current_buffer: list[str] = []
        chunk_idx = 0
        total_chars = 0

        def flush_buffer() -> None:
            nonlocal chunk_idx, total_chars
            section_text = "\n".join(current_buffer).strip()
            if section_text:
                total_chars += len(section_text)
                new_chunks = _chunk_text(
                    text=section_text,
                    doc_id=doc_id,
                    doc_name=filename,
                    page_number=None,
                    section_title=current_section,
                    start_index=chunk_idx,
                )
                chunks.extend(new_chunks)
                chunk_idx += len(new_chunks)
            current_buffer.clear()

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                flush_buffer()
                current_section = text
            else:
                current_buffer.append(text)

        flush_buffer()

        file_stream.seek(0, io.SEEK_END)
        size = file_stream.tell()

        metadata = DocumentMetadata(
            doc_id=doc_id,
            filename=filename,
            file_type="docx",
            file_size_bytes=size,
            total_pages=None,
            total_chunks=len(chunks),
            char_count=total_chars,
        )
        return metadata, chunks
    except Exception as exc:
        if isinstance(exc, DocumentParseError):
            raise
        raise DocumentParseError(f"Failed to parse DOCX '{filename}': {exc}") from exc


def parse_plain_text(
    file_bytes: bytes, doc_id: str, filename: str, ext: str
) -> tuple[DocumentMetadata, list[DocumentChunk]]:
    """Extracts text from plain text or markdown files."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        text = _clean_text(text)
        chunks = _chunk_text(
            text=text,
            doc_id=doc_id,
            doc_name=filename,
            page_number=None,
            section_title="Document Body",
            start_index=0,
        )
        metadata = DocumentMetadata(
            doc_id=doc_id,
            filename=filename,
            file_type="md" if ext == "md" else "txt",
            file_size_bytes=len(file_bytes),
            total_pages=None,
            total_chunks=len(chunks),
            char_count=len(text),
        )
        return metadata, chunks
    except Exception as exc:
        raise DocumentParseError(
            f"Failed to parse text document '{filename}': {exc}"
        ) from exc


def parse_uploaded_file(
    filename: str, file_bytes: bytes
) -> tuple[DocumentMetadata, list[DocumentChunk]]:
    """Unified entrypoint to validate and parse an uploaded file stream."""
    doc_id, ext = validate_upload(filename, file_bytes)
    stream = io.BytesIO(file_bytes)

    if ext == "pdf":
        return parse_pdf(stream, doc_id, filename)
    elif ext == "docx":
        return parse_docx(stream, doc_id, filename)
    else:
        return parse_plain_text(file_bytes, doc_id, filename, ext)


def _clean_text(raw_text: str) -> str:
    """Removes null bytes, normalizes whitespace, and strips non-printable control characters."""
    text = raw_text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(
    text: str,
    doc_id: str,
    doc_name: str,
    page_number: int | None,
    section_title: str | None,
    start_index: int,
) -> list[DocumentChunk]:
    """Splits text into overlapping bounded chunks."""
    if not text:
        return []

    chunks: list[DocumentChunk] = []
    start = 0
    idx = start_index

    while start < len(text):
        end = start + CHUNK_SIZE_CHARS
        if end >= len(text):
            chunk_content = text[start:].strip()
            if chunk_content:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{doc_id}_c{idx}",
                        doc_id=doc_id,
                        doc_name=doc_name,
                        page_number=page_number,
                        section_title=section_title,
                        content=chunk_content,
                        chunk_index=idx,
                        token_count_approx=len(chunk_content) // 4,
                    )
                )
            break

        # Look for natural paragraph or sentence boundary
        split_at = text.rfind("\n\n", start, end)
        if split_at == -1 or split_at <= start + CHUNK_OVERLAP_CHARS:
            split_at = text.rfind(". ", start, end)
        if split_at == -1 or split_at <= start + CHUNK_OVERLAP_CHARS:
            split_at = end

        chunk_content = text[start:split_at].strip()
        if chunk_content:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page_number=page_number,
                    section_title=section_title,
                    content=chunk_content,
                    chunk_index=idx,
                    token_count_approx=len(chunk_content) // 4,
                )
            )
            idx += 1

        start = max(start + 1, split_at - CHUNK_OVERLAP_CHARS)

    return chunks
