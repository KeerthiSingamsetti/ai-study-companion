import { useCallback, useEffect, useState } from 'react'
import { Menu } from 'lucide-react'
import { getDocuments, getThreads, removeThread, renameThread } from './api/client'
import WorkspaceGate from './components/WorkspaceGate'
import { WorkspaceProvider } from './context/WorkspaceContext'
import SidebarContainer from './components/Sidebar/SidebarContainer'
import WorkspaceRouter from './components/WorkspaceRouter'
import TopBar from './components/Header/TopBar'

function AppContent({ user, space, project, onProject, onSpace, switchProject, logout }) {
  const [threads, setThreads] = useState([])
  const activeThreadId = project.id

  const setActiveThreadId = useCallback(
    async (id) => {
      if (!id) {
        switchProject()
        return
      }
      const selected = threads.find((thread) => thread.id === id)
      if (selected) {
        onProject(selected)
        return
      }
      // Deep links from dashboards may target a project in another Space;
      // resolve it before falling back to the picker.
      try {
        const all = await getThreads()
        const target = all.find((thread) => thread.id === id)
        if (target) onProject(target)
      } catch {
        /* keep the current project when the lookup fails */
      }
    },
    [threads, onProject, switchProject],
  )

  const [documents, setDocuments] = useState([])

  /* Sidebar layout state */
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(288)
  const [isResizingSidebar, setIsResizingSidebar] = useState(false)
  const [chatResetKey, setChatResetKey] = useState(0)

  /* Left Sidebar Resizing Drag Handler */
  const startSidebarResize = useCallback((e) => {
    e.preventDefault()
    setIsResizingSidebar(true)

    const onMouseMove = (moveEvent) => {
      const newWidth = Math.min(Math.max(moveEvent.clientX, 220), 460)
      setSidebarWidth(newWidth)
    }

    const onMouseUp = () => {
      setIsResizingSidebar(false)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [])

  /* Initial data load */
  const loadThreads = useCallback(async () => {
    try {
      const data = await getThreads(space.id)
      setThreads(data)
    } catch (err) {
      console.error('Could not load projects:', err)
    }
  }, [space.id])

  const loadDocuments = useCallback(
    async (targetThreadId = activeThreadId) => {
      if (!targetThreadId || targetThreadId === 'undefined') {
        setDocuments([])
        return
      }
      try {
        const data = await getDocuments(targetThreadId)
        setDocuments(data)
      } catch {
        setDocuments([])
      }
    },
    [activeThreadId],
  )

  useEffect(() => {
    let alive = true
    getThreads(space.id)
      .then((data) => {
        if (alive) setThreads(data)
      })
      .catch(console.error)
    getDocuments(activeThreadId)
      .then((data) => {
        if (alive) setDocuments(data)
      })
      .catch(console.error)
    return () => {
      alive = false
    }
  }, [space.id, activeThreadId])

  /* Thread actions */
  function handleNewChat() {
    setActiveThreadId(null)
    setChatResetKey((prev) => prev + 1)
  }

  function handleSelectThread(id) {
    setActiveThreadId(id)
    setChatResetKey((prev) => prev + 1)
  }

  const handleThreadCreated = useCallback(
    (newId) => {
      setActiveThreadId(newId)
      void loadThreads()
    },
    [loadThreads, setActiveThreadId],
  )

  async function handleRenameThread(threadId, newTitle) {
    try {
      await renameThread(threadId, newTitle)
      setThreads((prev) => prev.map((t) => (t.id === threadId ? { ...t, title: newTitle } : t)))
    } catch (err) {
      alert(`Failed to rename thread: ${err.message}`)
    }
  }

  async function handleDeleteThread(threadId) {
    try {
      await removeThread(threadId)
      setThreads((prev) => prev.filter((t) => t.id !== threadId))
      if (activeThreadId === threadId) {
        handleNewChat()
      }
    } catch (err) {
      alert(`Failed to delete thread: ${err.message}`)
    }
  }

  const handleInvalidThread = useCallback(
    (invalidId) => {
      setThreads((prev) => prev.filter((t) => t.id !== invalidId))
      if (activeThreadId === invalidId) {
        setActiveThreadId(null)
        setChatResetKey((prev) => prev + 1)
      }
    },
    [activeThreadId, setActiveThreadId],
  )

  return (
    <WorkspaceProvider value={{ activeThreadId, setActiveThreadId, userRole: user?.role }}>
      <main className={`h-screen w-screen overflow-hidden bg-[var(--bg)] text-[var(--text-primary)] ${isResizingSidebar ? 'cursor-col-resize select-none' : ''}`}>
        <div className="flex h-full w-full overflow-hidden">
          {/* Unified ChatGPT/Claude-style Left Sidebar */}
          {isSidebarOpen && (
            <SidebarContainer
              user={user}
              threads={threads}
              onCreate={handleNewChat}
              onSelect={handleSelectThread}
              onRename={handleRenameThread}
              onDelete={handleDeleteThread}
              onClose={() => setIsSidebarOpen(false)}
              style={{ width: `${sidebarWidth}px` }}
              startResize={startSidebarResize}
              isResizing={isResizingSidebar}
            />
          )}

          {/* Main Content Area — Single Active Workspace */}
          <div className="relative flex flex-1 flex-col overflow-hidden bg-[var(--bg)]">
            {/* Sticky Glass Top Header Bar — single breadcrumb: Space > Project > page */}
            <div className="relative z-30 flex shrink-0 items-center">
              {!isSidebarOpen && (
                <button
                  type="button"
                  onClick={() => setIsSidebarOpen(true)}
                  className="absolute left-4 z-40 grid size-8 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-1)]/90 text-[var(--text-secondary)] transition hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
                  title="Show sidebar"
                  aria-label="Show sidebar"
                >
                  <Menu className="size-4" />
                </button>
              )}
              <TopBar
                space={space}
                project={project}
                user={user}
                onSelectSpace={onSpace}
                onSelectProject={onProject}
                onSignOut={logout}
              />
            </div>

            {/* Router Rendering Single Workspace via Visibility Toggling */}
            <WorkspaceRouter
              user={user}
              documents={documents}
              loadDocuments={loadDocuments}
              loadThreads={loadThreads}
              handleInvalidThread={handleInvalidThread}
              handleThreadCreated={handleThreadCreated}
              chatResetKey={chatResetKey}
            />
          </div>
        </div>
      </main>
    </WorkspaceProvider>
  )
}

export default function App() {
  return <WorkspaceGate>{(selection) => <AppContent key={selection.project.id} {...selection} />}</WorkspaceGate>
}
