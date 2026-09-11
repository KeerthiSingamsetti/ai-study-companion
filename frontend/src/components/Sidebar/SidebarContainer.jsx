import { useState } from 'react'
import { Plus, Search, X, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import WorkspaceSection from './WorkspaceSection'
import ChatSection from './ChatSection'

function CloseSidebarIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

export default function SidebarContainer({
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
        className="hidden shrink-0 border-r border-white/5 bg-[#0b0b14]/90 p-4 md:flex md:flex-col h-full overflow-hidden backdrop-blur-2xl transition-colors font-sans"
      >
        {/* Header */}
        <div className="mb-5 flex shrink-0 items-center justify-between px-1">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-2xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-violet-500 font-bold text-white shadow-lg shadow-violet-500/25 border border-white/10">
              <Sparkles className="size-4" />
            </div>
            <div>
              <p className="font-bold tracking-tight text-white text-sm">StudyMate AI</p>
              <p className="text-[11px] text-[var(--text-muted)] font-medium">Workspace</p>
            </div>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl p-1.5 text-[var(--text-muted)] transition hover:bg-white/5 hover:text-white"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
            >
              <CloseSidebarIcon />
            </button>
          )}
        </div>

        {/* New Chat Button with Animated Gradient */}
        <motion.button
          whileHover={{ scale: 1.02, y: -1 }}
          whileTap={{ scale: 0.98 }}
          type="button"
          onClick={onCreate}
          className="mb-3.5 flex shrink-0 items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-violet-600 via-indigo-600 to-violet-500 px-4 py-3 text-xs font-bold text-white shadow-lg shadow-violet-600/30 border border-white/15 transition-all hover:brightness-110 focus:outline-none"
        >
          <Plus className="size-4" />
          <span>New Chat</span>
        </motion.button>

        {/* Chat Glass Search Input */}
        <div className="mb-4 relative flex shrink-0 items-center">
          <Search className="absolute left-3 size-3.5 text-[var(--text-muted)] pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations…"
            className="w-full rounded-xl border border-white/10 bg-white/[0.03] py-2 pl-8 pr-7 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none transition focus:border-[var(--accent)]/50 focus:bg-white/[0.06] focus:ring-2 focus:ring-[var(--accent)]/20"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 rounded-md p-0.5 text-[var(--text-muted)] hover:bg-white/10 hover:text-white"
              title="Clear search"
            >
              <X className="size-3" />
            </button>
          )}
        </div>

        {/* Workspaces Section */}
        <WorkspaceSection />

        {/* Chats Section */}
        <ChatSection
          threads={threads}
          isLoading={isLoading}
          error={error}
          searchQuery={searchQuery}
          onSelect={onSelect}
          onRename={onRename}
          onDelete={onDelete}
        />
      </aside>

      {/* Resizable Splitter Handle */}
      {startResize && (
        <div
          onMouseDown={startResize}
          className={`w-1 cursor-col-resize hover:bg-violet-500/50 transition-colors ${
            isResizing ? 'bg-violet-500 shadow-glow' : 'bg-transparent'
          }`}
          title="Drag to resize sidebar width"
        />
      )}
    </div>
  )
}
