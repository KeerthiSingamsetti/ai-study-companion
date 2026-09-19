import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, RefreshCw, Trash2, UploadCloud } from 'lucide-react'
import { getDocuments, getIngestionJobs, removeDocument, retryIngestionJob, uploadDocuments } from '../api/client'
import { EmptyState, JobStatePill, PageHeader } from './ui/primitives'

/* ── Skeleton row ───────────────────────────────────────── */
function SkeletonRow() {
  return (
    <li className="flex items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-3.5">
      <div className="skeleton size-9 shrink-0 rounded-xl" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-3 w-2/3 rounded" />
        <div className="skeleton h-2.5 w-1/3 rounded" />
      </div>
    </li>
  )
}

/* ── Main component ─────────────────────────────────────── */
export default function DocumentPanel({ threadId, onDocumentUploaded }) {
  const [documents, setDocuments] = useState([])
  const [jobs, setJobs] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const [error, setError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [retryingJob, setRetryingJob] = useState(null)
  const fileInputRef = useRef(null)

  const loadJobs = useCallback(async () => {
    if (!threadId || threadId === 'undefined') {
      setJobs([])
      return
    }
    try {
      setJobs(await getIngestionJobs(threadId))
    } catch {
      setJobs([])
    }
  }, [threadId])

  /* Load documents + jobs whenever threadId changes */
  useEffect(() => {
    if (!threadId || threadId === 'undefined') {
      setDocuments([])
      setJobs([])
      return
    }

    let cancelled = false
    setIsLoading(true)
    setError('')
    getDocuments(threadId)
      .then((docs) => {
        if (!cancelled) setDocuments(docs)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    void loadJobs()
    return () => {
      cancelled = true
    }
  }, [threadId, loadJobs])

  /* Poll while any job is still moving through the pipeline. Documents are
     refetched alongside jobs so counts fill in the moment ingestion lands. */
  const loadDocuments = useCallback(async () => {
    if (!threadId || threadId === 'undefined') return
    try {
      setDocuments(await getDocuments(threadId))
    } catch {
      /* keep the current list on transient errors */
    }
  }, [threadId])

  useEffect(() => {
    const isPending = jobs.some((job) => job.status === 'queued' || job.status === 'processing')
    if (!isPending) return undefined
    const timer = setInterval(() => {
      void loadJobs()
      void loadDocuments()
    }, 4000)
    return () => clearInterval(timer)
  }, [jobs, loadJobs, loadDocuments])

  /* Upload logic */
  const handleUpload = useCallback(
    async (files) => {
      const pdfs = [...files].filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))
      if (pdfs.length === 0) {
        setUploadError('Only PDF files are accepted.')
        return
      }
      setUploadError('')
      setIsUploading(true)
      try {
        const result = await uploadDocuments(threadId, pdfs)
        setDocuments((prev) => [...prev, ...result.documents])
        await loadJobs()
        if (onDocumentUploaded) onDocumentUploaded()
      } catch (err) {
        setUploadError(err.message)
      } finally {
        setIsUploading(false)
      }
    },
    [threadId, loadJobs, onDocumentUploaded],
  )

  /* Delete logic */
  async function handleDelete(doc) {
    if (!window.confirm(`Remove "${doc.filename}" from this project?`)) return
    try {
      await removeDocument(doc.id)
      setDocuments((prev) => prev.filter((document) => document.id !== doc.id))
      await loadJobs()
      if (onDocumentUploaded) onDocumentUploaded()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleRetry(jobId) {
    setRetryingJob(jobId)
    try {
      await retryIngestionJob(jobId)
      await loadJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setRetryingJob(null)
    }
  }

  /* Drag-and-drop handlers */
  function onDragOver(e) {
    e.preventDefault()
    setIsDragOver(true)
  }
  function onDragLeave() {
    setIsDragOver(false)
  }
  function onDrop(e) {
    e.preventDefault()
    setIsDragOver(false)
    void handleUpload(e.dataTransfer.files)
  }

  if (!threadId) {
    return (
      <EmptyState
        icon={FileText}
        title="No project selected"
        description="Choose or create a project first — materials belong to a project so retrieval stays isolated."
      />
    )
  }

  const jobFor = (documentId) => jobs.filter((job) => job.document_id === documentId).at(-1)

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader
        icon={FileText}
        title="Learning Materials"
        subtitle="Upload course PDFs. Each file is parsed, chunked and indexed in the background so the Tutor can cite it."
      />

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
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-[var(--radius-card)] border-2 border-dashed px-6 py-9 text-center transition-all ${
          isDragOver
            ? 'scale-[1.01] border-[var(--accent)] bg-[var(--accent-soft)]'
            : 'border-[var(--border)] bg-[var(--surface-1)]/50 hover:border-[var(--accent)]/40 hover:bg-[var(--surface-1)]'
        }`}
      >
        <span className="grid size-12 place-items-center rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)]">
          <UploadCloud className="size-5" />
        </span>
        <p className="font-display text-sm font-semibold text-[var(--text-primary)]">
          {isUploading ? 'Uploading…' : 'Drop PDFs here or click to browse'}
        </p>
        <p className="text-xs text-[var(--text-muted)]">PDF only · multiple files supported · indexing continues in the background</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="hidden"
          onChange={(e) => void handleUpload(e.target.files)}
        />
      </div>

      {isUploading && (
        <div className="flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3.5 py-2.5">
          <span className="size-3 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
          <span className="text-xs font-medium text-[var(--accent)]">Sending your files…</span>
        </div>
      )}

      {uploadError && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          {uploadError}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          {error}
        </p>
      )}

      {/* Document list */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            Uploaded documents
          </p>
          <span className="font-mono-numbers text-xs text-[var(--text-muted)]">{documents.length}</span>
        </div>

        <ul className="space-y-2">
          {isLoading ? (
            <>
              <SkeletonRow />
              <SkeletonRow />
            </>
          ) : documents.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No documents yet"
              description="Upload a text-based PDF to give the Tutor something to ground its answers in."
            />
          ) : (
            documents.map((doc) => {
              const job = jobFor(doc.id)
              return (
                <li
                  key={doc.id}
                  className="group flex items-start gap-3.5 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-3.5 transition hover:border-[var(--border-strong)]"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)]">
                    <FileText className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium text-[var(--text-primary)]" title={doc.filename}>
                        {doc.filename}
                      </p>
                      {job && <JobStatePill state={job.status} />}
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {job && (job.status === 'queued' || job.status === 'processing')
                        ? (job.progress?.phase === 'embedding'
                          ? `Indexing ${job.progress.processed_chunks ?? 0}/${job.progress.total_chunks ?? '?'} chunks…`
                          : 'Parsing PDF…')
                        : `${doc.page_count ?? '?'} pages · ${doc.chunk_count ?? '?'} chunks`}
                      {job?.retry_count ? ` · retried ${job.retry_count}×` : ''}
                    </p>
                    {job?.status === 'failed' && job.error_msg && (
                      <p className="mt-1 text-[11px] text-[var(--danger)]">{job.error_msg}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    {job?.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => handleRetry(job.id)}
                        disabled={retryingJob === job.id}
                        className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2 py-1 text-[10px] font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)] disabled:opacity-50"
                        title="Retry failed ingestion"
                      >
                        <RefreshCw className={`size-3 ${retryingJob === job.id ? 'animate-spin' : ''}`} /> Retry
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => void handleDelete(doc)}
                      className="rounded-lg p-1.5 text-[var(--text-muted)] opacity-0 transition hover:bg-[var(--danger-soft)] hover:text-[var(--danger)] group-hover:opacity-100 focus-visible:opacity-100"
                      aria-label={`Delete ${doc.filename}`}
                      title="Delete document"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </li>
              )
            })
          )}
        </ul>
      </div>
    </div>
  )
}
