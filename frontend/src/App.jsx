import { useCallback, useEffect, useState } from 'react'
import { getDocuments, getThreads, removeThread, renameThread } from './api/client'
import { getStudyProgress } from './lib/progressApi'
import { WorkspaceProvider } from './context/WorkspaceContext'
import SidebarContainer from './components/Sidebar/SidebarContainer'
import WorkspaceRouter from './components/WorkspaceRouter'
import TopBar from './components/Header/TopBar'


function AppContent() {
  const [threads, setThreads] = useState([])
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [documents, setDocuments] = useState([])

  /* Sidebar layout state */
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(280)
  const [isResizingSidebar, setIsResizingSidebar] = useState(false)
  const [chatResetKey, setChatResetKey] = useState(0)


  /* Left Sidebar Resizing Drag Handler */
  const startSidebarResize = useCallback((e) => {
    e.preventDefault()
    setIsResizingSidebar(true)

    const onMouseMove = (moveEvent) => {
      const newWidth = Math.min(Math.max(moveEvent.clientX, 200), 450)
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
      const data = await getThreads()
      setThreads(data)
    } catch {
      /* ignore */
    }
  }, [])

  const loadDocuments = useCallback(async (targetThreadId = activeThreadId) => {
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
  }, [activeThreadId])

  /* Load user progress */
  const loadProgress = useCallback(async () => {
    try {
      const data = await getStudyProgress()
      if (data) setProgressData(data)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    void loadThreads()
    void loadDocuments(activeThreadId)
    void loadProgress()
  }, [loadThreads, loadDocuments, loadProgress, activeThreadId])

  /* Thread actions */
  function handleNewChat() {
    setActiveThreadId(null)
    setChatResetKey((prev) => prev + 1)
  }

  function handleSelectThread(id) {
    setActiveThreadId(id)
    setChatResetKey((prev) => prev + 1)
  }

  const handleThreadCreated = useCallback((newId) => {
    setActiveThreadId(newId)
    void loadThreads()
  }, [loadThreads])

  async function handleRenameThread(threadId, newTitle) {
    try {
      await renameThread(threadId, newTitle)
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? { ...t, title: newTitle } : t))
      )
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

  const handleInvalidThread = useCallback((invalidId) => {
    setThreads((prev) => prev.filter((t) => t.id !== invalidId))
    if (activeThreadId === invalidId) {
      setActiveThreadId(null)
      setChatResetKey((prev) => prev + 1)
    }
  }, [activeThreadId])

  return (
    <WorkspaceProvider value={{ activeThreadId, setActiveThreadId }}>
      <main className={`h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 ${isResizingSidebar ? 'select-none cursor-col-resize' : ''}`}>
        <div className="flex h-full w-full overflow-hidden">
          {/* Unified ChatGPT/Claude-style Left Sidebar */}
          {isSidebarOpen && (
            <SidebarContainer
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
          <div className="relative flex flex-1 flex-col overflow-hidden bg-[#09090F]">
            {/* Sticky Glass Top Header Bar */}
            <div className="flex items-center">
              {!isSidebarOpen && (
                <button
                  type="button"
                  onClick={() => setIsSidebarOpen(true)}
                  className="z-40 absolute top-4 left-4 grid size-8 place-items-center rounded-xl border border-white/10 bg-[#09090F]/90 text-[var(--text-secondary)] hover:bg-white/10 hover:text-white transition"
                  title="Show sidebar"
                >
                  <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
              <TopBar />
            </div>

            {/* Router Rendering Single Workspace via Visibility Toggling */}
            <WorkspaceRouter
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
  return <AppContent />
}
