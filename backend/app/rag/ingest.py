"""
PDF Ingestion for the StudyMate RAG pipeline.
"""

import tempfile
import os
import logging
import re
from typing import Tuple, Dict, Any, List, Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.rag.exceptions import PDFIngestError

from langsmith import traceable

logger = logging.getLogger(__name__)

_FIGURE_REFERENCE_PATTERN = re.compile(
    # Captures the full label including optional chapter prefix, e.g. "7-1" or just "1"
    r"\bfig(?:ure)?\.?\s*((?:\d+\s*-\s*)?\d+)(?=[:.\s]|$)",
    re.IGNORECASE,
)
_FIGURE_CAPTION_PATTERN = re.compile(
    r"(?im)^\s*fig(?:ure)?\.?\s*((?:\d+\s*-\s*)?\d+)(?=[:.\s]|$)",
)


def annotate_figure_metadata(chunks: List[Document]) -> None:
    """Tag chunks that mention figures and identify caption chunks.

    The ``figure_label`` field stores the full label (e.g. '7-1') for precise
    matching in the retriever.  ``figure_number`` retains the trailing integer
    for backwards-compatible filters.  ``figure_numbers`` preserves every
    trailing integer referenced in a body chunk.
    """
    for chunk in chunks:
        matches = list(_FIGURE_REFERENCE_PATTERN.finditer(chunk.page_content))
        if not matches:
            continue

        # Normalise: strip whitespace around dashes
        import re as _re
        labels = [_re.sub(r"\s*-\s*", "-", m.group(1).strip()) for m in matches]
        trailing_numbers = [int(label.split("-")[-1]) for label in labels]

        caption_match = _FIGURE_CAPTION_PATTERN.search(chunk.page_content)
        primary_label = _re.sub(r"\s*-\s*", "-", caption_match.group(1).strip()) if caption_match else labels[0]
        primary_number = int(primary_label.split("-")[-1])

        chunk.metadata["figure_label"] = primary_label          # e.g. '7-1'
        chunk.metadata["figure_number"] = primary_number        # e.g. 1  (trailing int)
        chunk.metadata["figure_numbers"] = list(dict.fromkeys(trailing_numbers))
        chunk.metadata["is_caption"] = caption_match is not None


"""
Note: load_and_chunk_pdf expects to be called within an active trace context; 
wrap callers with @traceable to unify the tree.
"""
@traceable(
    run_type="chain", 
    name="load_and_chunk_pdf",
    process_inputs=lambda inputs: {"filename": inputs.get("filename", "unknown")},
    process_outputs=lambda outputs: {"chunk_count": outputs[1].get("chunk_count")} if outputs and len(outputs) == 2 else {}
)
def load_and_chunk_pdf(
    file_bytes: bytes,
    filename: Optional[str] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 100
) -> Tuple[List[Document], Dict[str, Any]]:
    """
    Parses a PDF from bytes, extracts text, and chunks it for vector indexing.
    
    Defaults:
    - chunk_size = 500: Provides focused chunks for precise academic retrieval.
    - chunk_overlap = 100: Ensures boundaries between concepts are not severed,
      giving the LLM sufficient context overlap without bloating token usage.
      
    Args:
        file_bytes: The raw bytes of the uploaded PDF file.
        filename: Optional real filename. If provided, overrides the 'source' 
                  metadata in the chunks (preventing temp file path leaks). Callers 
                  integrating with the real ingestion flow should always pass this.
        chunk_size: Maximum length of characters per chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.
        
    Returns:
        A tuple of (chunks, metadata_summary):
        - chunks: List of LangChain Document objects with intact page metadata.
        - metadata_summary: Dict containing 'page_count' and 'chunk_count'.
        
    Raises:
        PDFIngestError: If the file is empty, cannot be parsed, or contains no text.
    """
    if not file_bytes:
        raise PDFIngestError("Provided PDF bytes are empty.")
        
    # Write bytes safely to a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(temp_fd, 'wb') as f:
            f.write(file_bytes)
            
        loader = PyPDFLoader(temp_path)
        try:
            docs = loader.load()
        except Exception as e:
            raise PDFIngestError(f"Failed to parse PDF: {str(e)}") from e
            
        # This check only catches a zero-page PDF (a completely empty document skeleton).
        # Scanned/image-only PDFs (real pages, but no extractable text) will bypass this
        # because PyPDFLoader returns Document objects with empty page_content.
        if not docs:
            raise PDFIngestError("PDF was parsed but contained zero pages.")
            
        if filename:
            for doc in docs:
                doc.metadata["source"] = filename
            
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )
        
        chunks = splitter.split_documents(docs)
        
        # This check catches scanned/image-only PDFs where pages had no extractable text,
        # resulting in the splitter producing zero text chunks.
        if not chunks:
            raise PDFIngestError("PDF splitting resulted in zero chunks. Ensure the PDF contains extractable text, not just images.")

        # Make retrieval filters and persisted-index provenance deterministic.
        # PyPDFLoader already supplies zero-based `page`; keep that convention.
        for chunk_index, chunk in enumerate(chunks):
            chunk.metadata.setdefault("chunk_id", f"{chunk.metadata.get('source', filename or 'document')}:{chunk_index}")
            chunk.metadata["chunk_index"] = chunk_index
            chunk.metadata.setdefault("chunk_size", chunk_size)
            chunk.metadata.setdefault("chunk_overlap", chunk_overlap)

        annotate_figure_metadata(chunks)
            
        metadata_summary = {
            "page_count": len(docs),
            "chunk_count": len(chunks)
        }
        
        return chunks, metadata_summary
        
    finally:
        # Guarantee cleanup even if exceptions occur
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as e:
                logger.warning(f"Failed to clean up temporary PDF file {temp_path}: {e}")
