import { useState } from 'react'
import { ChevronDown, MessageSquare } from 'lucide-react'
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
  const filteredThreads = query
    ? threads.filter((t) => (t.title || '').toLowerCase().includes(query))
    : threads


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
    <div className="flex-1 flex flex-col min-h-0">
      {/* Section Header */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-200 transition-colors shrink-0"
      >
        <span>Chats</span>
        <ChevronDown
          className={`size-3.5 transition-transform duration-200 ${
            isOpen ? 'rotate-0' : '-rotate-90'
          }`}
        />
      </button>

      {/* Collapsible Content */}
      <div
        className={`grid transition-all duration-300 ease-in-out min-h-0 ${
          isOpen ? 'grid-rows-[1fr] opacity-100 mt-1 flex-1' : 'grid-rows-[0fr] opacity-0'
        }`}
      >
        <div className="overflow-y-auto pr-1">
          {isLoading && <p className="px-2 py-3 text-xs text-slate-500">Loading chats…</p>}
          {error && <p className="px-2 py-3 text-xs text-rose-300">{error}</p>}

          {!isLoading && !error && threads.length === 0 && (
            <p className="px-2 py-3 text-xs leading-5 text-slate-500">Start a chat to create your first conversation.</p>
          )}

          {!isLoading && !error && threads.length > 0 && filteredThreads.length === 0 && (
            <p className="px-2 py-3 text-xs leading-5 text-slate-500">No chats found matching "{searchQuery}".</p>
          )}

          <ul className="space-y-1">
            {filteredThreads.map((thread) => (

              <li key={thread.id} className="group">
                {editingThreadId === thread.id ? (
                  <form
                    className="flex gap-1 rounded-lg bg-slate-800 p-1"
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
                      className="min-w-0 flex-1 rounded bg-slate-900 px-2 py-1 text-xs text-white outline-none ring-violet-400 focus:ring-1"
                    />
                    <button type="submit" className="rounded px-2 text-[10px] font-medium text-violet-200 hover:bg-slate-700">
                      Save
                    </button>
                  </form>
                ) : (
                  <div
                    className={`flex items-center gap-1 rounded-lg px-2 py-1.5 transition ${
                      activeThreadId === thread.id ? 'bg-slate-800 text-white font-medium' : 'text-slate-300 hover:bg-slate-800/60'
                    }`}
                  >
                    <button
                      type="button"
                      title={thread.title}
                      onClick={() => handleSelectThread(thread.id)}
                      className="min-w-0 flex-1 truncate text-left text-xs"
                    >
                      <span className="block truncate">{thread.title}</span>
                      <span className="block text-[10px] text-slate-500">{formatUpdatedAt(thread.updated_at)}</span>
                    </button>
                    <div className="hidden shrink-0 gap-1 group-hover:flex">
                      <button
                        type="button"
                        onClick={() => beginRename(thread)}
                        className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-white"
                        aria-label={`Rename ${thread.title}`}
                        title="Rename"
                      >
                        ✎
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm(`Delete “${thread.title}”? This also removes its document indexes.`)) {
                            if (onDelete) void onDelete(thread.id)
                          }
                        }}
                        className="rounded p-1 text-slate-400 hover:bg-rose-500/20 hover:text-rose-300"
                        aria-label={`Delete ${thread.title}`}
                        title="Delete"
                      >
                        ×
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
