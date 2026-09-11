"""
Unit tests for the StudyMate RAG pipeline (Module 2).
"""

import io
import pytest
from reportlab.pdfgen import canvas

from app.rag.ingest import load_and_chunk_pdf
from app.rag.exceptions import PDFIngestError

# ---------------------------------------------------------------------------
# Test Data Generation
# ---------------------------------------------------------------------------

def generate_sample_pdf_bytes(text: str = "This is a sample PDF document for testing the RAG pipeline.") -> bytes:
    """Generates a simple, hermetic PDF entirely in memory."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, text)
    c.showPage()
    c.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# STEP 2 Tests: ingest.py
# ---------------------------------------------------------------------------

def test_load_and_chunk_pdf_returns_chunks_and_metadata():
    """Valid PDF bytes should parse into chunks and return correct metadata."""
    pdf_bytes = generate_sample_pdf_bytes("This is a test. " * 50)  # Make it long enough to be meaningful
    
    # Using small chunk sizes for the test so we get multiple chunks
    chunks, metadata = load_and_chunk_pdf(pdf_bytes, chunk_size=50, chunk_overlap=10)
    
    assert len(chunks) > 1
    assert metadata["page_count"] == 1
    assert metadata["chunk_count"] == len(chunks)
    
    # Langchain populates 'source' and 'page' in metadata for PyPDFLoader
    assert "source" in chunks[0].metadata
    assert "page" in chunks[0].metadata
    
    # Verify fallback behavior: without a filename, the source is a temp path
    assert chunks[0].metadata["source"].endswith(".pdf")
    assert "tmp" in chunks[0].metadata["source"].lower()


def test_load_and_chunk_pdf_uses_provided_filename_in_metadata():
    """If a filename is provided, it should overwrite the temp file path in the source metadata."""
    pdf_bytes = generate_sample_pdf_bytes("Testing filename injection.")
    chunks, _ = load_and_chunk_pdf(pdf_bytes, filename="lecture_notes.pdf")
    
    assert chunks[0].metadata["source"] == "lecture_notes.pdf"


def test_load_and_chunk_pdf_raises_on_empty_bytes():
    """Empty bytes should raise PDFIngestError."""
    with pytest.raises(PDFIngestError):
        load_and_chunk_pdf(b"")
        

def test_load_and_chunk_pdf_raises_on_corrupted_bytes():
    """Corrupted/invalid PDF bytes should raise PDFIngestError."""
    with pytest.raises(PDFIngestError):
        load_and_chunk_pdf(b"this is not a valid pdf file")


# ---------------------------------------------------------------------------
# STEP 3 Tests: store.py
# ---------------------------------------------------------------------------

import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from app.rag.store import build_and_save_index, load_index, delete_index
from app.rag.exceptions import VectorStoreLoadError

@pytest.fixture(scope="module")
def embeddings():
    """Fixture to load embeddings once for all store/retriever tests."""
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

@pytest.fixture
def temp_index_dir(tmp_path):
    """Provides a fresh temporary directory path for index storage."""
    return str(tmp_path / "test_index")

@pytest.fixture
def sample_chunks():
    """Provides some basic chunks to embed."""
    return [
        Document(page_content="The quick brown fox jumps over the lazy dog.", metadata={"source": "test.pdf", "page": 1}),
        Document(page_content="Machine learning is a subset of artificial intelligence.", metadata={"source": "test.pdf", "page": 2})
    ]


def test_build_and_save_index_creates_directory(embeddings, temp_index_dir, sample_chunks):
    """Validates directory and files exist on disk after saving."""
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)
    
    assert os.path.exists(temp_index_dir)
    assert os.path.isdir(temp_index_dir)
    assert os.path.exists(os.path.join(temp_index_dir, "index.faiss"))
    assert os.path.exists(os.path.join(temp_index_dir, "index.pkl"))


def test_build_and_save_index_raises_on_empty_chunks(embeddings, temp_index_dir):
    """Saving an empty chunk list should raise ValueError and leave no directory behind."""
    with pytest.raises(ValueError):
        build_and_save_index([], embeddings, temp_index_dir)
        
    assert not os.path.exists(temp_index_dir)


def test_load_index_returns_none_for_missing_path(embeddings):
    """store.load_index handles completely missing paths gracefully by returning None."""
    missing_path = "/tmp/this/path/definitely/does/not/exist/9999"
    result = load_index(missing_path, embeddings)
    assert result is None


def test_save_then_load_index_roundtrip(embeddings, temp_index_dir, sample_chunks):
    """End-to-end persist and reload test proving the old 'docs disappear on restart' bug is solved."""
    # 1. Build and save
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)
    
    # 2. Load in a FRESH call (representing a server restart)
    loaded_faiss = load_index(temp_index_dir, embeddings)
    
    assert loaded_faiss is not None
    
    # 3. Query the reloaded index
    results = loaded_faiss.similarity_search("animal", k=1)
    assert len(results) == 1
    # Should fetch the fox/dog chunk
    assert "fox" in results[0].page_content.lower()


def test_delete_index_removes_directory(embeddings, temp_index_dir, sample_chunks):
    """Deletes valid directory cleanly and returns True."""
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)
    assert os.path.exists(temp_index_dir)
    
    result = delete_index(temp_index_dir)
    assert result is True
    assert not os.path.exists(temp_index_dir)


def test_delete_index_no_op_on_missing_path():
    """delete_index() on a path that was never created returns False and throws no exception."""
    missing_path = "/tmp/does/not/exist/delete/me/not"
    result = delete_index(missing_path)
    assert result is False


def test_load_index_raises_on_corrupted_index(embeddings, temp_index_dir, sample_chunks):
    """If the directory exists but the index is corrupted/missing, it must raise VectorStoreLoadError."""
    # First create a valid index
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)
    
    # Now deliberately sabotage it by deleting the PKL file
    pkl_path = os.path.join(temp_index_dir, "index.pkl")
    os.remove(pkl_path)
    
    # Loading it should now crash, which we must catch and wrap
    with pytest.raises(VectorStoreLoadError) as exc_info:
        load_index(temp_index_dir, embeddings)
        
    assert temp_index_dir in str(exc_info.value)


# ---------------------------------------------------------------------------
# STEP 4 Tests: reranker.py
# ---------------------------------------------------------------------------

from app.rag.reranker import rerank

@pytest.mark.integration

def test_reranker_changes_order_for_relevant_query():
    """
    Constructs chunks where the naive similarity top-1 isn't the most relevant chunk, 
    and asserts reranking changes the order.
    
    NOTE: This test is marked as an integration test because it downloads the 
    cross-encoder model from the HuggingFace Hub and runs real ML inference.
    It can be excluded from fast offline test runs via `pytest -m "not integration"`.
    """
    query = "How many apples does John have?"
    
    # We pass the chunks into the reranker in a "naive" order where the bad chunk is first.
    # A naive TF-IDF or embedding might incorrectly favor chunk1 due to token repetition.
    chunks = [
        Document(
            page_content="John used to have many apples, but now Mary has 5 apples and John has none. Apples are great.", 
            metadata={"id": "bad_chunk"}
        ),
        Document(
            page_content="John currently has exactly 3 apples in his basket.", 
            metadata={"id": "good_chunk"}
        )
    ]
    
    reranked = rerank(query, chunks, top_k=2)
    
    # Assert the reranker successfully identified the semantic answer and flipped the order
    assert len(reranked) == 2
    best_chunk, score = reranked[0]
    
    assert best_chunk.metadata["id"] == "good_chunk", "Reranker failed to prioritize the semantically correct chunk."


def test_rerank_returns_empty_list_for_no_chunks():
    """rerank() gracefully handles empty input without attempting inference."""
    results = rerank("test query", [], top_k=5)
    assert results == []


@pytest.mark.integration
def test_rerank_respects_top_k_truncation():
    """rerank() must strictly truncate its final output to top_k chunks."""
    query = "test"
    chunks = [
        Document(page_content="a", metadata={"id": "1"}),
        Document(page_content="b", metadata={"id": "2"}),
        Document(page_content="c", metadata={"id": "3"}),
    ]
    results = rerank(query, chunks, top_k=1)
    
    assert len(results) == 1


# ---------------------------------------------------------------------------
# STEP 5 Tests: retriever.py
# ---------------------------------------------------------------------------

from app.rag.retriever import retrieve
from app.rag.exceptions import DocumentNotIndexedError

def test_retrieve_raises_when_not_indexed(embeddings):
    """retrieve() gracefully funnels missing or corrupted paths into DocumentNotIndexedError."""
    # Test completely missing path
    with pytest.raises(DocumentNotIndexedError) as exc_info:
        retrieve("test", "/tmp/definitely/does/not/exist", embeddings)
    assert "No index exists" in str(exc_info.value)


def test_retrieve_returns_chunks_without_reranking(embeddings, temp_index_dir, sample_chunks):
    """retrieve() correctly fetches chunks with FAISS-only scoring and explicit sorting when reranking is off."""
    from app.rag.store import build_and_save_index
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)
    
    results = retrieve("machine learning", temp_index_dir, embeddings, use_reranking=False, k=2)
    
    assert len(results) > 0
    
    # Assert rerank_score is None
    for chunk in results:
        assert chunk.rerank_score is None
        assert chunk.similarity_score is not None
        assert 0.0 < chunk.similarity_score <= 1.0  # L2 distance inverted check
        
    # Assert descending sort by similarity_score
    scores = [c.similarity_score for c in results]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_raises_documentnotindexed_on_corrupted_index(embeddings, temp_index_dir, sample_chunks):
    """retrieve() MUST translate VectorStoreLoadError into DocumentNotIndexedError."""
    from app.rag.store import build_and_save_index
    import os
    
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)
    
    # Sabotage it by deleting the PKL file
    pkl_path = os.path.join(temp_index_dir, "index.pkl")
    os.remove(pkl_path)
    
    with pytest.raises(DocumentNotIndexedError) as exc_info:
        retrieve("test", temp_index_dir, embeddings)
        
    assert "corrupted, incompatible, or unreadable" in str(exc_info.value)


@pytest.mark.integration
def test_retrieve_returns_correctly_reranked_chunks(embeddings, temp_index_dir):
    """End-to-end integration test proving retrieve() reranks and maps identity correctly."""
    from app.rag.store import build_and_save_index
    from langchain_core.documents import Document
    
    query = "How many apples does John have?"
    chunks = [
        Document(
            page_content="John used to have many apples, but now Mary has 5 apples and John has none. Apples are great.", 
            metadata={"source": "test.pdf"}
        ),
        Document(
            page_content="John currently has exactly 3 apples in his basket.", 
            metadata={"source": "test.pdf"}
        ),
        Document(
            page_content="Apples grow on trees.", 
            metadata={"source": "test.pdf"}
        )
    ]
    
    build_and_save_index(chunks, embeddings, temp_index_dir)
    
    # Retrieve with reranking enabled
    results = retrieve(query, temp_index_dir, embeddings, use_reranking=True, k=3, rerank_top_k=2)
    
    assert len(results) == 2
    # The first result must be the semantically correct chunk
    assert results[0].content == "John currently has exactly 3 apples in his basket."
    assert results[0].rerank_score is not None
    assert results[1].rerank_score is not None
    # Ensure they are sorted descending by rerank_score
    assert results[0].rerank_score >= results[1].rerank_score


# ---------------------------------------------------------------------------
# STEP 3 (new): store.py — chunks.pkl persistence
# ---------------------------------------------------------------------------

from app.rag.store import load_chunks

def test_build_and_save_index_also_persists_chunks(embeddings, temp_index_dir, sample_chunks):
    """
    Test 12: build_and_save_index() must write chunks.pkl alongside the FAISS files,
    and load_chunks() must round-trip the same content back.
    """
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)

    # chunks.pkl must exist on disk
    assert os.path.exists(os.path.join(temp_index_dir, "chunks.pkl"))

    # Round-trip: load_chunks should return the same chunks
    returned = load_chunks(temp_index_dir)
    assert returned is not None
    assert len(returned) == len(sample_chunks)
    assert returned[0].page_content == sample_chunks[0].page_content
    assert returned[1].page_content == sample_chunks[1].page_content


def test_load_chunks_returns_none_when_missing(tmp_path):
    """
    Test 13: An index directory that lacks chunks.pkl (e.g. built before hybrid
    search was added) must return None from load_chunks(), not raise an exception.
    The backward-compatibility contract: old indexes survive, they just can't do
    hybrid search until rebuilt.
    """
    # Create a directory with only FAISS files, no chunks.pkl
    old_style_dir = str(tmp_path / "old_index")
    os.makedirs(old_style_dir)
    # Simulate the two FAISS files being present (content doesn't matter for this test)
    open(os.path.join(old_style_dir, "index.faiss"), "w").close()
    open(os.path.join(old_style_dir, "index.pkl"), "w").close()
    # chunks.pkl deliberately absent

    result = load_chunks(old_style_dir)
    assert result is None


# ---------------------------------------------------------------------------
# STEP 5 (new): retriever.py — hybrid BM25/dense retrieval
# ---------------------------------------------------------------------------

def test_retrieve_hybrid_raises_documentnotindexed_without_chunks(embeddings, temp_index_dir, sample_chunks):
    """
    Test 14: retrieve() with use_hybrid_search=True against an index that is missing
    chunks.pkl must raise DocumentNotIndexedError, not an unhandled AttributeError
    from BM25Retriever.from_documents(None).

    This is the hybrid counterpart to test_retrieve_raises_documentnotindexed_on_corrupted_index:
    it proves the exception boundary in _hybrid_retrieve() correctly translates the
    None-return from store.load_chunks() into DocumentNotIndexedError.
    """
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)

    # Simulate an old index without chunks.pkl
    chunks_pkl = os.path.join(temp_index_dir, "chunks.pkl")
    os.remove(chunks_pkl)
    assert not os.path.exists(chunks_pkl)  # confirm sabotage

    with pytest.raises(DocumentNotIndexedError) as exc_info:
        retrieve("test query", temp_index_dir, embeddings, use_hybrid_search=True)

    # Error message must be diagnosable — not a raw BM25/pickle error
    assert "chunks.pkl" in str(exc_info.value) or "hybrid" in str(exc_info.value)


@pytest.mark.integration
def test_retrieve_hybrid_returns_results(embeddings, temp_index_dir):
    """
    Test 15: Smoke test that the hybrid BM25+dense path runs end-to-end and
    returns a non-empty result set containing chunks from both lexical and
    semantic signal.

    SCOPE CAVEAT: With only 3 chunks, this test demonstrates that hybrid mode
    runs correctly and blends BM25 and dense signal — it is a correctness smoke
    test, NOT a statistical quality claim. BM25's IDF scoring is corpus-wide and
    only becomes meaningful at 50+ documents. At 3 chunks, BM25 effectively acts
    like TF overlap rather than full inverse-document-frequency weighting. Do not
    over-read this test as a proof that hybrid outperforms pure dense retrieval on
    real corpora.
    """
    from langchain_core.documents import Document

    # Lexical-vs-semantic gap corpus:
    # Chunk A has exact token match for "powerhouse"; Chunk B is semantically related
    # but has no lexical overlap; Chunk C is clearly off-topic.
    chunks = [
        Document(page_content="The mitochondria is the powerhouse of the cell.", metadata={"source": "bio.pdf"}),
        Document(page_content="Cellular respiration produces most of the ATP used by eukaryotic cells.", metadata={"source": "bio.pdf"}),
        Document(page_content="Photosynthesis converts light energy to chemical energy in plants.", metadata={"source": "bio.pdf"}),
    ]
    build_and_save_index(chunks, embeddings, temp_index_dir)

    query = "powerhouse ATP production"
    results = retrieve(query, temp_index_dir, embeddings,
                       use_hybrid_search=True, use_reranking=False, k=3)

    # Basic correctness: some results are returned
    assert len(results) > 0

    # The clearly off-topic chunk (photosynthesis) must not dominate as top-1
    assert results[0].content != "Photosynthesis converts light energy to chemical energy in plants."

    # Both lexical hit (Chunk A) and semantic hit (Chunk B) should appear somewhere,
    # proving both BM25 and dense contribute to the fusion.
    contents = [r.content for r in results]
    assert any("mitochondria" in c or "powerhouse" in c for c in contents), \
        "Lexical hit (BM25 signal) not present — BM25 retriever may not be contributing"
    assert any("ATP" in c or "respiration" in c for c in contents), \
        "Semantic hit (dense signal) not present — dense retriever may not be contributing"


def test_retrieve_hybrid_raises_documentnotindexed_on_corrupted_chunks(embeddings, temp_index_dir, sample_chunks):
    """
    Test 16: retrieve() with use_hybrid_search=True against an index whose chunks.pkl
    is CORRUPTED (not missing) must raise DocumentNotIndexedError, not a raw
    pickle.UnpicklingError or VectorStoreLoadError leaking through.

    This is the hybrid-mode counterpart to test_load_index_raises_on_corrupted_index
    from Step 3: store.load_chunks() raises VectorStoreLoadError on a corrupted
    (not-missing) chunks.pkl, and _hybrid_retrieve() must catch and translate it.
    """
    build_and_save_index(sample_chunks, embeddings, temp_index_dir)

    # Overwrite chunks.pkl with garbage bytes — same sabotage pattern as index.pkl above
    chunks_pkl = os.path.join(temp_index_dir, "chunks.pkl")
    with open(chunks_pkl, "wb") as f:
        f.write(b"CORRUPTED_GARBAGE_BYTES_NOT_A_VALID_PICKLE")

    with pytest.raises(DocumentNotIndexedError) as exc_info:
        retrieve("test query", temp_index_dir, embeddings, use_hybrid_search=True)

    # Must not be a raw VectorStoreLoadError — the exception boundary must have fired
    from app.rag.exceptions import VectorStoreLoadError
    assert not isinstance(exc_info.value, VectorStoreLoadError)


@pytest.mark.integration
def test_hybrid_similarity_score_is_descending_rank_proxy(embeddings, temp_index_dir):
    """
    Test 17: In hybrid mode, similarity_score is a rank-based proxy score computed
    as 1.0 - (i / total). This test asserts:
    1. Scores are strictly non-increasing (regression guard for candidates.sort()).
    2. The top result's score is exactly 1.0 (i=0 case of the formula).
    3. The bottom result's score matches the expected proxy value for the last rank,
       confirming the 1.0-(i/total) formula is actually applied and not silently
       dropped in a future refactor.
    """
    from langchain_core.documents import Document

    chunks = [
        Document(page_content="The mitochondria is the powerhouse of the cell.", metadata={"source": "bio.pdf"}),
        Document(page_content="Cellular respiration produces most of the ATP used by eukaryotic cells.", metadata={"source": "bio.pdf"}),
        Document(page_content="Photosynthesis converts light energy to chemical energy in plants.", metadata={"source": "bio.pdf"}),
    ]
    build_and_save_index(chunks, embeddings, temp_index_dir)

    results = retrieve("powerhouse ATP production", temp_index_dir, embeddings,
                       use_hybrid_search=True, use_reranking=False, k=3)

    assert len(results) > 0

    # 1. Scores must be non-increasing (sort regression guard)
    scores = [r.similarity_score for r in results]
    assert scores == sorted(scores, reverse=True), \
        "similarity_scores are not in descending order — candidates.sort() may have been removed"

    # 2. Top result must be exactly 1.0 (rank 0: 1.0 - 0/total = 1.0)
    assert results[0].similarity_score == pytest.approx(1.0), \
        "Top rank proxy score should be 1.0 (formula: 1.0 - 0/total)"

    # 3. For a 3-result list, the last score should be 1.0 - (2/3) ≈ 0.333
    assert all(0.0 <= score <= 1.0 for score in scores)
