import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, LogOut, Sparkles } from 'lucide-react'
import { useWorkspace } from '../../context/WorkspaceContext'
import { WORKSPACE_TOOLS } from '../../config/toolRegistry'
import { getSpaces, getThreads } from '../../api/client'

const panelClass =
  'absolute left-0 top-full z-50 mt-2 w-80 max-w-[85vw] overflow-hidden rounded-2xl border border-[var(--border-strong)] bg-[var(--surface-1)] p-2 shadow-[var(--shadow-pop)]'
const itemClass =
  'block w-full rounded-xl px-3 py-2.5 text-left transition hover:bg-white/[0.06]'
const newClass =
  'mt-1 block w-full rounded-xl px-3 py-2.5 text-left text-xs font-bold text-[var(--accent)] transition hover:bg-[var(--accent-soft)]'

/**
 * Breadcrumb dropdown listing every Space (or every Project in the current
 * Space) with its description, so switching context is an informed choice
 * rather than a guess at a name.
 */
function Switcher({ label, kind, spaceId, onSelect, onNew, icon: Icon }) {
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
    load
      .then((data) => {
        if (alive) setItems(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
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
    <span ref={wrapRef} className="relative min-w-0">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex min-w-0 max-w-[220px] items-center gap-2 rounded-xl border border-transparent px-2 py-1.5 text-sm font-bold text-[var(--text-primary)] transition hover:border-[var(--border)] hover:bg-white/[0.05]"
        title={kind === 'space' ? 'Switch Space' : 'Switch project'}
      >
        {Icon && <Icon className="size-3.5 shrink-0 text-[var(--text-muted)]" />}
        <span className="truncate">{label}</span>
        <ChevronDown className={`size-3.5 shrink-0 text-[var(--text-muted)] transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className={panelClass}>
          <p className="px-3 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {kind === 'space' ? 'Your Spaces' : 'Projects in this Space'}
          </p>

          <div className="max-h-72 overflow-y-auto">
            {error && <p className="px-3 py-2 text-xs text-[var(--danger)]">{error}</p>}
            {!error && items === null && <p className="px-3 py-2 text-xs text-[var(--text-muted)]">Loading…</p>}
            {Array.isArray(items) && items.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--text-muted)]">Nothing here yet.</p>
            )}
            {Array.isArray(items) &&
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setOpen(false)
                    onSelect(item)
                  }}
                  className={itemClass}
                >
                  <span className="block truncate text-sm font-semibold text-[var(--text-primary)]">
                    {item.name || item.title}
                  </span>
                  {item.description && (
                    <span className="mt-0.5 block truncate text-[11px] text-[var(--text-muted)]">{item.description}</span>
                  )}
                  {item.learning_goal && (
                    <span className="mt-0.5 block truncate text-[11px] text-[var(--accent)]/80">Goal: {item.learning_goal}</span>
                  )}
                </button>
              ))}
          </div>

          {Array.isArray(items) && (
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                onNew()
              }}
              className={newClass}
            >
              {kind === 'space' ? '+ New Space' : '+ New project'}
            </button>
          )}
        </div>
      )}
    </span>
  )
}

function initialsOf(name = '') {
  const parts = String(name).trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase()
}

export default function TopBar({ space, project, user, onSelectSpace, onSelectProject, onSignOut }) {
  const { activeWorkspace } = useWorkspace()

  const currentTool = WORKSPACE_TOOLS.find((tool) => tool.id === activeWorkspace) || WORKSPACE_TOOLS[0]
  const Icon = currentTool.icon

  return (
    <header className="sticky top-0 z-30 flex h-[72px] w-full shrink-0 items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--bg)]/85 px-5 backdrop-blur-xl">
      {/* ── Left: Space → Project breadcrumb with the active workspace beneath ── */}
      <div className="flex min-w-0 flex-col justify-center gap-1">
        <div className="flex min-w-0 items-center gap-1">
          <Switcher label={space?.name ?? 'Space'} kind="space" onSelect={onSelectSpace} onNew={() => onSelectSpace(null)} />
          <ChevronRight className="size-4 shrink-0 text-[var(--text-muted)]/60" />
          <Switcher
            label={project?.title ?? 'Project'}
            kind="project"
            spaceId={space?.id}
            onSelect={onSelectProject}
            onNew={() => onSelectProject(null)}
          />
        </div>

        <div className="flex min-w-0 items-center gap-2 pl-2 text-xs">
          <Icon className="size-3.5 shrink-0 text-[var(--accent)]" />
          <span className="truncate font-semibold text-[var(--text-secondary)]">{currentTool.title}</span>
          <span className="hidden truncate text-[var(--text-muted)] lg:inline">· {currentTool.description}</span>
        </div>
      </div>

      {/* ── Right: workspace status + account ─────────────────────────── */}
      <div className="flex shrink-0 items-center gap-2.5">
        <span className="hidden items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-[var(--accent)] md:inline-flex">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent)] opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-[var(--accent)]" />
          </span>
          {currentTool.shortName} ready
        </span>

        {user && (
          <span className="hidden items-center gap-2.5 rounded-full border border-[var(--border)] bg-[var(--surface-1)] py-1 pl-1 pr-3.5 sm:inline-flex">
            <span className="grid size-8 shrink-0 place-items-center rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[11px] font-bold text-[var(--accent)]">
              {initialsOf(user.display_name)}
            </span>
            <span className="min-w-0 leading-tight">
              <span className="block truncate text-xs font-semibold text-[var(--text-primary)]">{user.display_name}</span>
              <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                <Sparkles className="size-2.5" /> Student
              </span>
            </span>
          </span>
        )}

        {onSignOut && (
          <button
            type="button"
            onClick={onSignOut}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          >
            <LogOut className="size-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        )}
      </div>
    </header>
  )
}
