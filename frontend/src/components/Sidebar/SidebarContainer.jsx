import { useState } from 'react'
import { Plus, Search, Shield, X } from 'lucide-react'
import { motion } from 'framer-motion'
import WorkspaceSection from './WorkspaceSection'
import ChatSection from './ChatSection'
import { Logo } from '../ui/primitives'

function CloseSidebarIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

export default function SidebarContainer({
  user,
  threads = [],
  isLoading = false,
  error = null,
  onCreate,
  onSelect,
  onRename,
  onDelete,
  onClose,
  style,
  startResize,
  isResizing,
}) {
  const [searchQuery, setSearchQuery] = useState('')

  return (
    <div className="relative flex h-full shrink-0">
      <aside
        style={style}
        className="hidden h-full shrink-0 flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--surface-1)]/70 p-4 backdrop-blur-2xl md:flex"
      >
        {/* Header */}
        <div className="mb-5 flex shrink-0 items-center justify-between px-1">
          <Logo size={36} />
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl p-1.5 text-[var(--text-muted)] transition hover:bg-white/5 hover:text-[var(--text-primary)]"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
            >
              <CloseSidebarIcon />
            </button>
          )}
        </div>

        {/* Switch / create project */}
        <motion.button
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          type="button"
          onClick={onCreate}
          className="mb-3.5 flex shrink-0 items-center justify-center gap-2 rounded-[var(--radius-control)] border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-4 py-2.5 text-xs font-bold text-[var(--accent)] transition hover:border-[var(--accent)]/50 hover:bg-[var(--accent)]/20"
          title="Switch Space or project"
        >
          <Plus className="size-4" />
          <span>Switch / new project</span>
        </motion.button>

        {/* Conversation search */}
        <div className="relative mb-4 flex shrink-0 items-center">
          <Search className="pointer-events-none absolute left-3 size-3.5 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations…"
            aria-label="Search conversations"
            className="w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)]/60 py-2 pl-8 pr-7 text-xs text-[var(--text-primary)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]/50 focus:bg-[var(--surface-2)]"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 rounded-md p-0.5 text-[var(--text-muted)] hover:bg-white/10 hover:text-[var(--text-primary)]"
              title="Clear search"
              aria-label="Clear search"
            >
              <X className="size-3" />
            </button>
          )}
        </div>

        {/* Workspaces */}
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <WorkspaceSection />
          <ChatSection
            threads={threads}
            isLoading={isLoading}
            error={error}
            searchQuery={searchQuery}
            onSelect={onSelect}
            onRename={onRename}
            onDelete={onDelete}
          />
        </div>

        {/* Account footer */}
        {user && (
          <div className="mt-3 flex shrink-0 items-center gap-2.5 rounded-2xl border border-[var(--border)] bg-[var(--surface-2)]/50 px-3 py-2.5">
            <span className="grid size-8 shrink-0 place-items-center rounded-xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] text-xs font-bold text-[var(--accent)]">
              {(user.display_name || user.email || '?').slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold text-[var(--text-primary)]">{user.display_name}</span>
              <span className="block truncate text-[10px] text-[var(--text-muted)]">{user.email}</span>
            </span>
            {user.role === 'admin' && (
              <span
                className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[var(--accent)]"
                title="Platform administrator"
              >
                <Shield className="size-2.5" /> Admin
              </span>
            )}
          </div>
        )}
      </aside>

      {/* Resizable Splitter Handle */}
      {startResize && (
        <div
          onMouseDown={startResize}
          className={`w-1 cursor-col-resize transition-colors hover:bg-[var(--accent)]/50 ${
            isResizing ? 'bg-[var(--accent)]' : 'bg-transparent'
          }`}
          title="Drag to resize sidebar width"
        />
      )}
    </div>
  )
}
