import { Activity, ArrowRight } from 'lucide-react'

/**
 * Trimmed in-chat indicator for progress updates.
 * Renders a compact one-line summary banner with a button to open the full Progress workspace tab.
 */
export default function WeakTopicsCard({ progressData, onOpenProgressTab }) {
  if (!progressData) return null

  const weakCount = progressData.weak_topics?.length ?? 0

  return (
    <div className="my-2.5 flex flex-wrap items-center justify-between gap-2.5 rounded-xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-4 py-3 text-xs text-[var(--text-primary)]">
      <div className="flex items-center gap-2.5">
        <span className="grid size-7 place-items-center rounded-lg border border-[var(--accent)]/25 bg-[var(--accent)]/10 text-[var(--accent)]">
          <Activity className="size-3.5" />
        </span>
        <span>
          <span className="font-semibold">Study progress updated</span>
          <span className="ml-1.5 text-[var(--text-secondary)]">
            — {weakCount} topic{weakCount === 1 ? '' : 's'} currently needing review
          </span>
        </span>
      </div>

      <button
        type="button"
        onClick={onOpenProgressTab}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/15 px-3 py-1.5 font-semibold text-[var(--accent)] transition hover:bg-[var(--accent)]/25"
      >
        <span>Open Progress</span>
        <ArrowRight className="size-3" />
      </button>
    </div>
  )
}
