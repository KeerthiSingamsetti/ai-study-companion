import { BookOpen, FileText } from 'lucide-react'

/**
 * Compact citation badge component rendering sources as pill badges at the bottom of messages.
 * Citations are a core product promise: every grounded answer names its document and page.
 */
export default function CitationBadges({ sources = [], parsedSources = [] }) {
  const combined = []
  const seen = new Set()

  const addSource = (doc, page) => {
    if (!doc) return
    const cleanDoc = doc.trim()
    const key = `${cleanDoc.toLowerCase()}:${page ?? ''}`
    if (!seen.has(key)) {
      seen.add(key)
      combined.push({ document: cleanDoc, page })
    }
  }

  for (const s of sources) {
    addSource(s.document, s.page)
  }
  for (const s of parsedSources) {
    addSource(s.document, s.page)
  }

  if (combined.length === 0) return null

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-3 text-xs">
      <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
        <BookOpen className="size-3.5 text-[var(--accent)]" />
        Sources ({combined.length})
      </span>
      <div className="flex flex-wrap items-center gap-1.5">
        {combined.map((src, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-3 py-1 text-xs font-medium text-[var(--accent)] transition-colors hover:border-[var(--accent)]/50"
          >
            <FileText className="size-3 shrink-0" />
            <span className="max-w-[200px] truncate">{src.document}</span>
            {src.page != null && (
              <span className="rounded bg-[var(--accent)]/20 px-1.5 py-0.5 text-[10px] font-bold text-[var(--accent)]">
                p. {src.page}
              </span>
            )}
          </span>
        ))}
      </div>
    </div>
  )
}
