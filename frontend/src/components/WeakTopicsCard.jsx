import React from 'react'
import { Activity, ArrowRight } from 'lucide-react'

/**
 * Trimmed in-chat indicator for progress updates.
 * Renders a compact one-line summary banner with a button to open the full Progress workspace tab.
 */
export default function WeakTopicsCard({ progressData, onOpenProgressTab }) {
  if (!progressData) return null

  const weakCount = progressData.weak_topics?.length ?? 0

  return (
    <div className="my-2.5 flex flex-wrap items-center justify-between gap-2.5 rounded-xl border border-violet-500/20 bg-slate-950/60 px-4 py-3 text-xs text-slate-200 shadow-md backdrop-blur animate-fade-in">
      <div className="flex items-center gap-2">
        <div className="grid size-7 place-items-center rounded-lg bg-violet-500/10 text-violet-400 ring-1 ring-inset ring-violet-500/20">
          <Activity className="size-3.5" />
        </div>
        <div>
          <span className="font-semibold text-white">Study Progress Updated</span>
          <span className="text-slate-400 ml-1.5">— {weakCount} topic(s) currently needing review</span>
        </div>
      </div>

      <button
        type="button"
        onClick={onOpenProgressTab}
        className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500/15 px-3 py-1.5 font-semibold text-violet-300 ring-1 ring-inset ring-violet-500/20 transition-all hover:bg-violet-500/25 hover:text-white"
      >
        <span>Open Progress Workspace</span>
        <ArrowRight className="size-3" />

      </button>
    </div>
  )
}
