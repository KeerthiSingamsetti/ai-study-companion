import { useState } from 'react'
import { ChevronDown, MessageSquare, Pencil, Trash2 } from 'lucide-react'
import { useWorkspace } from '../../context/WorkspaceContext'

function formatUpdatedAt(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}

export default function ChatSection({
  threads = [],
  isLoading = false,
  error = null,
  searchQuery = '',
  onSelect,
  onRename,
  onDelete,
}) {
  const [isOpen, setIsOpen] = useState(true)
  const [editingThreadId, setEditingThreadId] = useState(null)
  const [editedTitle, setEditedTitle] = useState('')
  const { activeThreadId, setActiveWorkspace } = useWorkspace()

  const query = searchQuery.trim().toLowerCase()
  const filteredThreads = query ? threads.filter((t) => (t.title || '').toLowerCase().includes(query)) : threads

  function beginRename(thread) {
    setEditingThreadId(thread.id)
    setEditedTitle(thread.title)
  }

  async function saveRename(threadId) {
    const title = editedTitle.trim()
    if (!title) return
    if (onRename) await onRename(threadId, title)
    setEditingThreadId(null)
  }

  function handleSelectThread(id) {
    if (onSelect) onSelect(id)
    setActiveWorkspace('chat')
  }

  return (
    <div className="flex min-h-0 flex-col">
      {/* Section header */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full shrink-0 items-center justify-between px-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)] transition hover:text-[var(--text-primary)]"
      >
        <span>Conversations</span>
        <ChevronDown className={`size-3.5 transition-transform duration-200 ${isOpen ? 'rotate-0' : '-rotate-90'}`} />
      </button>

      {/* Collapsible content */}
      <div
        className={`grid min-h-0 transition-all duration-300 ease-in-out ${
          isOpen ? 'mt-1 grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
        }`}
      >
        <div className="overflow-y-auto pr-1">
          {isLoading && <p className="px-2 py-3 text-xs text-[var(--text-muted)]">Loading conversations…</p>}
          {error && <p className="px-2 py-3 text-xs text-[var(--danger)]">{error}</p>}

          {!isLoading && !error && threads.length === 0 && (
            <p className="px-2 py-3 text-xs leading-5 text-[var(--text-muted)]">
              Start a chat with the Tutor to create your first conversation.
            </p>
          )}

          {!isLoading && !error && threads.length > 0 && filteredThreads.length === 0 && (
            <p className="px-2 py-3 text-xs leading-5 text-[var(--text-muted)]">
              No conversations match “{searchQuery}”.
            </p>
          )}

          <ul className="space-y-0.5">
            {filteredThreads.map((thread) => (
              <li key={thread.id} className="group">
                {editingThreadId === thread.id ? (
                  <form
                    className="flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-1"
                    onSubmit={(event) => {
                      event.preventDefault()
                      void saveRename(thread.id)
                    }}
                  >
                    <input
                      autoFocus
                      value={editedTitle}
                      onChange={(event) => setEditedTitle(event.target.value)}
                      onBlur={(event) => {
                        if (!event.currentTarget.form?.contains(event.relatedTarget)) {
                          setEditingThreadId(null)
                        }
                      }}
                      maxLength="200"
                      className="min-w-0 flex-1 rounded-lg bg-[var(--surface-3)] px-2 py-1 text-xs text-[var(--text-primary)] outline-none ring-[var(--accent)]/60 focus:ring-1"
                    />
                    <button type="submit" className="rounded-lg px-2 text-[10px] font-semibold text-[var(--accent)] hover:bg-white/10">
                      Save
                    </button>
                  </form>
                ) : (
                  <div
                    className={`flex items-center gap-1 rounded-xl px-2 py-1.5 transition ${
                      activeThreadId === thread.id
                        ? 'border border-[var(--accent)]/25 bg-[var(--accent-soft)] text-[var(--text-primary)]'
                        : 'border border-transparent text-[var(--text-secondary)] hover:bg-white/[0.04]'
                    }`}
                  >
                    <MessageSquare className="size-3.5 shrink-0 text-[var(--text-muted)]" />
                    <button
                      type="button"
                      title={thread.title}
                      onClick={() => handleSelectThread(thread.id)}
                      className="min-w-0 flex-1 truncate text-left text-xs"
                    >
                      <span className="block truncate font-medium">{thread.title}</span>
                      <span className="block text-[10px] text-[var(--text-muted)]">{formatUpdatedAt(thread.updated_at)}</span>
                    </button>
                    <div className="hidden shrink-0 gap-0.5 group-hover:flex">
                      <button
                        type="button"
                        onClick={() => beginRename(thread)}
                        className="rounded-md p-1 text-[var(--text-muted)] transition hover:bg-white/10 hover:text-[var(--text-primary)]"
                        aria-label={`Rename ${thread.title}`}
                        title="Rename"
                      >
                        <Pencil className="size-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm(`Delete “${thread.title}”? This also removes its document indexes.`)) {
                            if (onDelete) void onDelete(thread.id)
                          }
                        }}
                        className="rounded-md p-1 text-[var(--text-muted)] transition hover:bg-[var(--danger-soft)] hover:text-[var(--danger)]"
                        aria-label={`Delete ${thread.title}`}
                        title="Delete"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
