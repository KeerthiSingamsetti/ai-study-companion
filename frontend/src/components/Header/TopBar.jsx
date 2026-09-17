import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useWorkspace } from '../../context/WorkspaceContext'
import { WORKSPACE_TOOLS } from '../../config/toolRegistry'
import { getSpaces, getThreads } from '../../api/client'

const panelClass = 'absolute left-0 top-full z-50 mt-2 w-64 rounded-2xl border border-white/10 bg-[#0b0b14] p-2 shadow-2xl'
const itemClass = 'block w-full truncate rounded-lg px-2.5 py-2 text-left text-xs text-[var(--text-secondary)] transition hover:bg-white/10 hover:text-white'
const newClass = 'mt-1 block w-full rounded-lg px-2.5 py-2 text-left text-xs font-semibold text-violet-300 transition hover:bg-violet-500/10'

// Dropdown segment listing ALL Spaces (or all Projects in the current Space).
function Switcher({ label, kind, spaceId, onSelect, onNew }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const wrapRef = useRef(null)

  function toggle() {
    if (!open) {
      // Reset before reopening so stale rows/error never flash.
      setItems(null)
      setError('')
    }
    setOpen((prev) => !prev)
  }

  useEffect(() => {
    if (!open) return undefined
    let alive = true
    const load = kind === 'space' ? getSpaces() : getThreads(spaceId)
    load.then((data) => { if (alive) setItems(data) })
      .catch((err) => { if (alive) setError(err.message) })
    return () => { alive = false }
  }, [open, kind, spaceId])

  useEffect(() => {
    if (!open) return undefined
    const onOutside = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [open])

  return (
    <span ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        className="flex max-w-[180px] items-center gap-1 rounded-lg px-1.5 py-0.5 font-semibold text-[var(--text-primary)] transition hover:bg-white/10"
        title={kind === 'space' ? 'Switch Space' : 'Switch project'}
      >
        <span className="truncate">{label}</span>
        <ChevronDown className={`size-3 shrink-0 text-[var(--text-muted)] transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className={panelClass}>
          {error && <p className="px-2.5 py-1.5 text-xs text-red-300">{error}</p>}
          {!error && items === null && <p className="px-2.5 py-1.5 text-xs text-[var(--text-muted)]">Loading…</p>}
          {Array.isArray(items) && items.length === 0 && (
            <p className="px-2.5 py-1.5 text-xs text-[var(--text-muted)]">Nothing here yet.</p>
          )}
          {Array.isArray(items) && items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => { setOpen(false); onSelect(item) }}
              className={itemClass}
            >
              {item.name || item.title}
            </button>
          ))}
          {Array.isArray(items) && (
            <button type="button" onClick={() => { setOpen(false); onNew() }} className={newClass}>
              {kind === 'space' ? '+ New Space' : '+ New project'}
            </button>
          )}
        </div>
      )}
    </span>
  )
}

export default function TopBar({ space, project, onSelectSpace, onSelectProject, onSignOut }) {
  const { activeWorkspace } = useWorkspace()

  // Find active tool config
  const currentTool = WORKSPACE_TOOLS.find((t) => t.id === activeWorkspace) || WORKSPACE_TOOLS[0]
  const Icon = currentTool.icon

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full shrink-0 items-center justify-between border-b border-white/5 bg-[#09090F]/80 px-6 backdrop-blur-xl font-sans transition-colors">
      {/* ── Left: Breadcrumbs & Current Tool Badge ─────────────────────── */}
      <div className="flex min-w-0 items-center gap-1.5 text-xs text-[var(--text-muted)] font-medium">
        <Switcher
          label={space?.name ?? 'Space'}
          kind="space"
          onSelect={onSelectSpace}
          onNew={() => onSelectSpace(null)}
        />
        <ChevronRight className="size-3 shrink-0 text-white/20" />
        <Switcher
          label={project?.title ?? 'Project'}
          kind="project"
          spaceId={space?.id}
          onSelect={onSelectProject}
          onNew={() => onSelectProject(null)}
        />
        <ChevronRight className="size-3 shrink-0 text-white/20" />
        <span className="flex shrink-0 items-center gap-1.5 font-semibold text-[var(--text-primary)]">
          <Icon className="size-3.5 text-[var(--accent)]" />
          {currentTool.title}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {/* Live Active Status Badge */}
        <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--accent)] uppercase tracking-wider">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent)] opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-[var(--accent)]" />
          </span>
          <span>{currentTool.shortName} AI</span>
        </span>

        {onSignOut && (
          <button
            type="button"
            onClick={onSignOut}
            className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-[var(--text-muted)] transition hover:bg-white/10 hover:text-white"
          >
            Sign out
          </button>
        )}
      </div>
    </header>
  )
}
