import React from 'react'
import { ChevronRight } from 'lucide-react'
import { useWorkspace } from '../../context/WorkspaceContext'
import { WORKSPACE_TOOLS } from '../../config/toolRegistry'

export default function TopBar() {
  const { activeWorkspace } = useWorkspace()

  // Find active tool config
  const currentTool = WORKSPACE_TOOLS.find((t) => t.id === activeWorkspace) || WORKSPACE_TOOLS[0]
  const Icon = currentTool.icon

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full shrink-0 items-center justify-between border-b border-white/5 bg-[#09090F]/80 px-6 backdrop-blur-xl font-sans transition-colors">
      {/* ── Left: Breadcrumbs & Current Tool Badge ─────────────────────── */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] font-medium">
          <span className="text-[var(--text-secondary)]">StudyMate</span>
          <ChevronRight className="size-3 text-white/20" />
          <span className="text-[var(--text-secondary)]">Workspace</span>
          <ChevronRight className="size-3 text-white/20" />
          <span className="flex items-center gap-1.5 font-semibold text-[var(--text-primary)]">
            <Icon className="size-3.5 text-[var(--accent)]" />
            {currentTool.title}
          </span>
        </div>

        {/* Live Active Status Badge */}
        <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--accent)] uppercase tracking-wider">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent)] opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-[var(--accent)]" />
          </span>
          <span>{currentTool.shortName} AI</span>
        </span>
      </div>
    </header>
  )
}
