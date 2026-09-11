import { useEffect, useState } from 'react'
import { getDocuments, queryRag } from '../api/client'

/* ── Score badge ────────────────────────────────────────── */
function ScoreBadge({ label, value, color }) {
  if (value == null) return null
  const pct = typeof value === 'number' && value <= 1 ? `${(value * 100).toFixed(0)}%` : value.toFixed(3)
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${color}`}>
      {label}: {pct}
    </span>
  )
}

/* ── Chunk result card ──────────────────────────────────── */
function ChunkCard({ chunk, index }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <li className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden animate-fade-in">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-slate-800/50"
      >
        <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-[10px] font-bold text-violet-300">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-medium text-slate-300 truncate max-w-[140px]" title={chunk.source}>
              {chunk.source?.split(/[\\/]/).pop() ?? chunk.source ?? 'Unknown'}
            </span>
            {chunk.page != null && (
              <span className="text-[10px] text-slate-600">p.{chunk.page}</span>
            )}
            <ScoreBadge
              label="sim"
              value={chunk.similarity_score}
              color="bg-violet-500/15 text-violet-300 ring-violet-400/20"
            />
            {chunk.rerank_score != null && (
              <ScoreBadge
                label="rerank"
                value={chunk.rerank_score}
                color="bg-emerald-500/15 text-emerald-300 ring-emerald-400/20"
              />
            )}
          </div>
          <p className="mt-0.5 line-clamp-1 text-xs text-slate-600">{chunk.content}</p>
        </div>
        <svg
          className={`size-4 shrink-0 text-slate-600 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-slate-800 bg-slate-950/60 px-4 py-3">
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-slate-400">
            {chunk.content ?? '(no content)'}
          </pre>
        </div>
      )}
    </li>
  )
}

/* ── Main Component ─────────────────────────────────────── */
export default function RagDebugPanel({ threadId }) {
  const [documents, setDocuments] = useState([])
  const [selectedDocId, setSelectedDocId] = useState('')
  const [query, setQuery] = useState('')
  const [k, setK] = useState(6)
  const [useReranking, setUseReranking] = useState(true)
  const [useHybrid, setUseHybrid] = useState(false)
  const [result, setResult] = useState(null)
  const [isQuerying, setIsQuerying] = useState(false)
  const [isLoadingDocs, setIsLoadingDocs] = useState(false)
  const [error, setError] = useState('')

  /* Load documents when thread changes (need vectorstore_path for index_path) */
  useEffect(() => {
    if (!threadId) { setDocuments([]); setSelectedDocId(''); setResult(null); return }
    let cancelled = false
    setIsLoadingDocs(true)
    getDocuments(threadId)
      .then((docs) => {
        if (!cancelled) {
          setDocuments(docs)
          setSelectedDocId(docs[0]?.id ?? '')
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setIsLoadingDocs(false) })
    return () => { cancelled = true }
  }, [threadId])

  const selectedDoc = documents.find((d) => d.id === selectedDocId)

  async function handleSubmit(e) {
    e.preventDefault()
    const q = query.trim()
    if (!q || isQuerying || !selectedDoc) return
    setError('')
    setIsQuerying(true)
    setResult(null)
    try {
      const data = await queryRag({
        query: q,
        index_path: selectedDoc.vectorstore_path,
        k,
        use_reranking: useReranking,
        use_hybrid_search: useHybrid,
        rerank_top_k: Math.min(k, 4),
      })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsQuerying(false)
    }
  }

  /* ── No thread ──────────────────────────────────────────── */
  if (!threadId) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center animate-fade-in">
        <div className="grid size-12 place-items-center rounded-2xl bg-slate-800 text-slate-500">
          <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 1-6.23-.693L5 14.5" />
          </svg>
        </div>
        <p className="text-sm font-medium text-slate-400">No thread selected</p>
        <p className="text-xs leading-5 text-slate-600">Select a conversation and upload a PDF to query its index.</p>
      </div>
    )
  }

  /* ── No documents uploaded yet ───────────────────────────── */
  if (!isLoadingDocs && documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center animate-fade-in">
        <p className="text-sm font-medium text-slate-400">No documents in this thread</p>
        <p className="text-xs leading-5 text-slate-600">Upload a PDF in the Documents tab first, then return here to query its index.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      {/* Info */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2.5">
        <p className="text-xs leading-5 text-slate-500">
          Inspect raw chunks from a document's FAISS index. Select a document, enter a query, and see what the retriever returns.
        </p>
      </div>

      {/* Query form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Document picker */}
        <div>
          <label htmlFor="rag-doc-select" className="mb-1 block text-xs font-medium text-slate-400">
            Document index
          </label>
          {isLoadingDocs ? (
            <div className="skeleton h-9 w-full rounded-lg" />
          ) : (
            <select
              id="rag-doc-select"
              value={selectedDocId}
              onChange={(e) => { setSelectedDocId(e.target.value); setResult(null) }}
              disabled={isQuerying}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-violet-500 disabled:opacity-60"
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename} ({doc.chunk_count ?? '?'} chunks)
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Query input */}
        <div>
          <label htmlFor="rag-query-input" className="mb-1 block text-xs font-medium text-slate-400">
            Query
          </label>
          <input
            id="rag-query-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. explain gradient descent"
            disabled={isQuerying}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-600 focus:border-violet-500 disabled:opacity-60"
          />
        </div>

        {/* Options row */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-20">
            <label htmlFor="rag-k" className="mb-1 block text-xs font-medium text-slate-400">Top-K</label>
            <input
              id="rag-k"
              type="number"
              min="1"
              max="20"
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
              disabled={isQuerying}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-violet-500 disabled:opacity-60"
            />
          </div>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={useReranking}
              onChange={(e) => setUseReranking(e.target.checked)}
              className="accent-violet-500"
            />
            Reranking
          </label>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={useHybrid}
              onChange={(e) => setUseHybrid(e.target.checked)}
              className="accent-violet-500"
            />
            Hybrid search
          </label>
          <button
            type="submit"
            disabled={!query.trim() || isQuerying || !selectedDoc}
            className="ml-auto rounded-lg bg-violet-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isQuerying ? (
              <span className="flex items-center gap-2">
                <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Querying…
              </span>
            ) : 'Query'}
          </button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{error}</p>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-3 animate-fade-in">
          {/* Grounded answer */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Grounded Answer</p>
            <p className="text-sm leading-6 text-slate-300">{result.answer}</p>
          </div>

          {/* Structured sources */}
          {result.sources && result.sources.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Sources</p>
              <div className="flex flex-wrap gap-1.5">
                {result.sources.map((src, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded bg-slate-800/80 px-2 py-0.5 text-[11px] font-medium text-violet-300 ring-1 ring-inset ring-violet-400/20"
                  >
                    📄 {src.document}{src.page != null ? `, p. ${src.page}` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Chunk list */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {result.num_chunks} chunk{result.num_chunks !== 1 ? 's' : ''} retrieved
            </p>
            <ul className="space-y-2">
              {result.retrieved_chunks.map((chunk, i) => (
                <ChunkCard key={i} chunk={chunk} index={i} />
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
