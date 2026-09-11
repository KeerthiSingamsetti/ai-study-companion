import { useCallback, useEffect, useRef, useState } from 'react'
import { getDocuments, removeDocument, uploadDocuments } from '../api/client'

/* ── Icon helpers (inline SVG) ─────────────────────────── */
function FileIcon() {
  return (
    <svg className="size-5 shrink-0 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0 1 16.138 21H7.862a2 2 0 0 1-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v3M4 7h16" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg className="size-8 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
    </svg>
  )
}

/* ── Skeleton row ───────────────────────────────────────── */
function SkeletonRow() {
  return (
    <li className="flex items-center gap-3 rounded-xl border border-slate-800/60 bg-slate-900/60 p-3">
      <div className="skeleton size-5 shrink-0 rounded" />
      <div className="flex-1 space-y-1.5">
        <div className="skeleton h-3 w-2/3 rounded" />
        <div className="skeleton h-2.5 w-1/3 rounded" />
      </div>
    </li>
  )
}

/* ── Main Component ─────────────────────────────────────── */
export default function DocumentPanel({ threadId }) {
  const [documents, setDocuments] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const [error, setError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const fileInputRef = useRef(null)
  /* Load docs whenever threadId changes */
  useEffect(() => {
    if (!threadId || threadId === 'undefined') { setDocuments([]); return }

    let cancelled = false
    setIsLoading(true)
    setError('')
    getDocuments(threadId)
      .then((docs) => {
        if (!cancelled) {
          setDocuments(docs)
        }
      })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setIsLoading(false) })
    return () => { cancelled = true }
  }, [threadId])

  /* Upload logic */
  const handleUpload = useCallback(async (files) => {
    const pdfs = [...files].filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length === 0) { setUploadError('Only PDF files are accepted.'); return }
    setUploadError('')
    setIsUploading(true)
    try {
      const result = await uploadDocuments(threadId, pdfs)
      setDocuments((prev) => {
        return [...prev, ...result.documents]
      })
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setIsUploading(false)
    }
  }, [threadId])

  /* Delete logic */
  async function handleDelete(doc) {
    if (!window.confirm(`Remove "${doc.filename}" from this thread?`)) return
    try {
      await removeDocument(doc.id)
      setDocuments((prev) => {
        return prev.filter((document) => document.id !== doc.id)
      })
    } catch (err) {
      setError(err.message)
    }
  }

  /* Drag-and-drop handlers */
  function onDragOver(e) { e.preventDefault(); setIsDragOver(true) }
  function onDragLeave() { setIsDragOver(false) }
  function onDrop(e) {
    e.preventDefault()
    setIsDragOver(false)
    void handleUpload(e.dataTransfer.files)
  }

  /* ── No thread selected state ──────────────────────────── */
  if (!threadId) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center animate-fade-in">
        <div className="grid size-12 place-items-center rounded-2xl bg-slate-800 text-slate-500">
          <FileIcon />
        </div>
        <p className="text-sm font-medium text-slate-400">No thread selected</p>
        <p className="text-xs leading-5 text-slate-600">Start a chat first, then upload PDFs to this thread.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      {/* Upload area */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload PDF files"
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed py-7 text-center transition-all ${
          isDragOver
            ? 'border-violet-400 bg-violet-500/10 scale-[1.02]'
            : 'border-slate-700 hover:border-slate-600 hover:bg-slate-800/40'
        }`}
      >
        <UploadIcon />
        <p className="text-sm font-medium text-slate-300">
          {isUploading ? 'Uploading…' : 'Drop PDFs here or click to browse'}
        </p>
        <p className="text-xs text-slate-600">PDF only · multiple files supported</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="hidden"
          onChange={(e) => void handleUpload(e.target.files)}
        />
      </div>

      {/* Upload progress */}
      {isUploading && (
        <div className="flex items-center gap-2 rounded-lg bg-violet-500/10 px-3 py-2">
          <span className="size-3 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
          <span className="text-xs text-violet-300">Processing & indexing…</span>
        </div>
      )}

      {/* Errors */}
      {uploadError && (
        <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{uploadError}</p>
      )}
      {error && (
        <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{error}</p>
      )}

      {/* Document list */}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Uploaded Documents
        </p>
        <ul className="space-y-2">
          {isLoading ? (
            <><SkeletonRow /><SkeletonRow /></>
          ) : documents.length === 0 ? (
            <li className="rounded-xl border border-dashed border-slate-800 px-4 py-6 text-center text-xs text-slate-600">
              No documents yet. Upload a PDF to get started.
            </li>
          ) : (
            documents.map((doc) => (
              <li
                key={doc.id}
                className="group flex items-start gap-3 rounded-xl border border-slate-800/60 bg-slate-900/60 p-3 transition hover:border-slate-700"
              >
                <FileIcon />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200" title={doc.filename}>
                    {doc.filename}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {doc.page_count ?? '?'} pages · {doc.chunk_count ?? '?'} chunks
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDelete(doc)}
                  className="shrink-0 rounded p-1 text-slate-600 opacity-0 transition hover:bg-rose-500/20 hover:text-rose-400 group-hover:opacity-100"
                  aria-label={`Delete ${doc.filename}`}
                  title="Delete document"
                >
                  <TrashIcon />
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  )
}
