import { useEffect, useRef, useState } from 'react'
import { getThreadMessages } from '../api/client'
import { sendChatMessageStream } from '../lib/api'
import { useWorkspace } from '../context/WorkspaceContext'
import ToolStatusIndicator from './ToolStatusIndicator'
import MarkdownMessage from './MarkdownMessage'
import CitationBadges from './CitationBadges'
import WeakTopicsCard from './WeakTopicsCard'


/**
 * Extracts Markdown body content separate from trailing Sources section.
 * Parses any inline text citations like "sample.pdf, p. 18" or "sample.pdf (page 18)".
 */
function parseBodyAndSources(rawContent = '') {
  if (!rawContent) return { body: '', parsedSources: [] }

  const sourcesPattern = /(?:^|\n)(?:##\s*(?:📚\s*)?Sources|\*\*Sources:\*\*|Sources:)([\s\S]*)$/i
  const match = rawContent.match(sourcesPattern)

  if (!match) {
    return { body: rawContent, parsedSources: [] }
  }

  const body = rawContent.slice(0, match.index).trim()
  const sourcesText = match[1] ?? ''
  const parsedSources = []

  const regex = /(?:📄\s*)?([a-zA-Z0-9_\-.]+\.pdf)(?:[^\n\d]*?(\d+))?/gi
  let m
  while ((m = regex.exec(sourcesText)) !== null) {
    const doc = m[1]?.trim()
    const page = m[2] ? parseInt(m[2], 10) : null
    if (doc) {
      parsedSources.push({ document: doc, page })
    }
  }

  return { body, parsedSources }
}

/* ── Typing indicator dots ──────────────────────────────── */
function TypingDots() {
  return (
    <span className="flex items-center gap-1" aria-label="StudyMate is responding">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="block size-1.5 rounded-full bg-slate-400"
          style={{ animation: `bounce-dot 1s ${delay}ms infinite ease-in-out` }}
        />
      ))}
    </span>
  )
}

/* ── Generic assistant-response indicator ───────────────── */
function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 text-sm text-slate-400 animate-fade-in">
      <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 text-xs font-bold text-white shadow-lg shadow-violet-500/20">
        S
      </div>
      <div className="flex items-center gap-2.5 rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-xs text-slate-300 shadow-md">
        <span className="relative flex size-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-violet-400 opacity-75" />
          <span className="relative inline-flex size-2 rounded-full bg-violet-500" />
        </span>
        <span className="font-medium text-slate-300">Thinking…</span>
        <TypingDots />
      </div>
    </div>
  )
}

/* ── Skeleton Message ───────────────────────────────────── */
function HistorySkeleton() {
  return (
    <div className="space-y-4 animate-fade-in py-4">
      <div className="flex gap-3 justify-end">
        <div className="skeleton h-10 w-2/3 rounded-2xl" />
      </div>
      <div className="flex gap-3 justify-start">
        <div className="skeleton size-8 rounded-lg" />
        <div className="skeleton h-16 w-3/4 rounded-2xl" />
      </div>
    </div>
  )
}

/* ── ChatWindow ─────────────────────────────────────────── */
function ChatWindow({
  onFlashcardsCreated,
  onPlanCreated,
  onInvalidThread,
  onQuizCreated,
  onProgressResult,
  onOpenProgressTab,
  onQuizTopic,
  onResponse,
  onThreadCreated,
  resetKey,
  threadId,
}) {
  const { activeWorkspace, setActiveWorkspace } = useWorkspace()

  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [messages, setMessages] = useState([])
  const scrollAnchorRef = useRef(null)
  const textareaRef = useRef(null)
  const pendingToolStatusRef = useRef(null)
  const createdThreadIdRef = useRef(null)

  /* Fetch history whenever threadId, resetKey, or activeWorkspace changes */
  useEffect(() => {
    if (activeWorkspace && activeWorkspace !== 'chat') {
      return
    }

    setDraft('')
    setError('')
    pendingToolStatusRef.current = null
    createdThreadIdRef.current = null

    if (!threadId || threadId === 'undefined') {
      setIsLoadingHistory(false)
      setMessages([])
      return
    }

    let isCurrent = true
    setIsLoadingHistory(true)

    getThreadMessages(threadId)
      .then((history) => {
        if (isCurrent) setMessages(history ?? [])
      })
      .catch((requestError) => {
        if (isCurrent) {
          if (requestError.status === 404 || requestError.message?.includes('not found')) {
            if (onInvalidThread) onInvalidThread(threadId)
          } else {
            setError(requestError.message)
          }
        }
      })
      .finally(() => {
        if (isCurrent) setIsLoadingHistory(false)
      })

    return () => {
      isCurrent = false
    }
  }, [threadId, resetKey, activeWorkspace, onInvalidThread])



  /* Auto-scroll */
  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isSending, isLoadingHistory])

  /* Auto-grow textarea */
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [draft])

  async function sendMessage() {
    const message = draft.trim()
    if (!message || isSending) return

    setDraft('')
    setError('')
    setIsSending(true)
    pendingToolStatusRef.current = null
    setMessages((prev) => [...prev, { content: message, role: 'user' }])

    try {
      await sendChatMessageStream(message, threadId, {
        onToolResult: (toolResult) => {
          if (toolResult && toolResult.tool === 'quiz') {
            pendingToolStatusRef.current = {
              message: '✅ Quiz created',
              detail: toolResult.topic,
            }
            if (onQuizCreated) onQuizCreated(toolResult)
            setActiveWorkspace('quiz')
          } else if (toolResult && toolResult.tool === 'flashcards') {
            pendingToolStatusRef.current = {
              message: '✅ Flashcards created',
              detail: toolResult.topic,
            }
            if (onFlashcardsCreated) onFlashcardsCreated(toolResult)
            setActiveWorkspace('flashcards')
          } else if (toolResult && (toolResult.tool === 'study_planner' || toolResult.tool === 'notes')) {
            pendingToolStatusRef.current = {
              message: toolResult.tool === 'notes' ? '✅ Notes generated' : '✅ Study plan created',
              detail: toolResult.topic,
            }
            if (onPlanCreated) onPlanCreated(toolResult)
            setActiveWorkspace('planner')
          } else if (toolResult && toolResult.tool === 'progress') {
            pendingToolStatusRef.current = {
              message: '📊 Study progress updated',
              detail: `${toolResult.weak_topics?.length ?? 0} weak topic(s) tracked`,
              progressData: toolResult,
            }
            if (onProgressResult) onProgressResult(toolResult)
            setActiveWorkspace('progress')
          }
        },


        onMessage: (response) => {
          const toolStatus = pendingToolStatusRef.current
          pendingToolStatusRef.current = null
          setMessages((prev) => [
            ...prev,
            {
              content: response.message,
              role: 'assistant',
              sources: response.sources ?? [],
              toolStatus,
              progressData: toolStatus?.progressData,
            },
          ])
          if (response.thread_id) {
            createdThreadIdRef.current = response.thread_id
            if (!threadId && onThreadCreated) {
              onThreadCreated(response.thread_id)
            }
          }
        },
      })
      if (onResponse) await onResponse()
    } catch (requestError) {
      if (requestError.status === 404 || requestError.message?.includes('not found')) {
        if (onInvalidThread) onInvalidThread(threadId)
      } else {
        setError(requestError.message)
      }
    } finally {
      setIsSending(false)
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }

  return (
    <section className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
      {/* ── Scrollable Message List ─────────────── */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col px-5 py-10">

          {isLoadingHistory ? (
            <HistorySkeleton />
          ) : messages.length === 0 ? (
            /* Empty state */
            <div className="my-auto py-16 animate-fade-in">
              <span className="mb-4 inline-flex rounded-full bg-violet-500/10 px-3 py-1 text-xs font-medium text-violet-300 ring-1 ring-inset ring-violet-400/20">
                StudyMate AI
              </span>
              <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                What would you like to learn today?
              </h1>
              <p className="mt-4 max-w-xl text-base leading-7 text-slate-400">
                Ask a question, upload a PDF, and keep your learning conversations organized in one place.
              </p>
              <div className="mt-8 flex flex-wrap gap-2">
                {[
                  'Explain this concept simply',
                  'Quiz me on this topic',
                  'Give me study tips',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => { setDraft(suggestion); textareaRef.current?.focus() }}
                    className="rounded-full border border-slate-700 bg-slate-900/60 px-4 py-1.5 text-sm text-slate-300 transition hover:border-violet-400/50 hover:bg-violet-500/10 hover:text-white"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message, index) => {
                const activeProgressData = message.progressData || message.progress_data

                return (
                  <article
                    key={`${message.role}-${index}`}
                    className={`flex gap-3 animate-fade-in ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {message.role === 'assistant' && (
                      <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 text-xs font-bold text-white shadow-lg shadow-violet-500/20">
                        S
                      </div>
                    )}
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                        message.role === 'user'
                          ? 'bg-gradient-to-br from-violet-500 to-violet-600 text-white shadow-lg shadow-violet-500/20'
                          : 'border border-slate-800 bg-slate-900 text-slate-200'
                      }`}
                    >
                      {message.role === 'assistant' ? (
                        <>
                          {/* 1. Header Text / Markdown Message */}
                          {(() => {
                            const { body, parsedSources } = parseBodyAndSources(message.content)
                            return (
                              <>
                                <MarkdownMessage content={body} />

                                {/* 2. Weak Topics Card Component */}
                                {activeProgressData && (
                                  <WeakTopicsCard
                                    progressData={activeProgressData}
                                    onOpenProgressTab={onOpenProgressTab}
                                  />
                                )}


                                {message.toolStatus && (
                                  <div className="mt-3 border-t border-slate-800/80 pt-2">
                                    <ToolStatusIndicator
                                      message={message.toolStatus.message}
                                      detail={message.toolStatus.detail}
                                    />
                                  </div>
                                )}
                                <CitationBadges
                                  sources={message.sources ?? []}
                                  parsedSources={parsedSources}
                                />
                              </>
                            )
                          })()}
                        </>
                      ) : (
                        message.content
                      )}
                    </div>
                  </article>
                )
              })}

              {isSending && <ThinkingIndicator />}
            </div>
          )}

          <div ref={scrollAnchorRef} />
        </div>
      </div>

      {/* ── Fixed Input bar ──────────────────────────────── */}
      <div className="shrink-0 border-t border-slate-800 bg-slate-950/80 px-5 py-4 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl">
          {error && (
            <p className="mb-2 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{error}</p>
          )}
          <div className="rounded-2xl border border-slate-700 bg-slate-900 p-3 shadow-2xl shadow-black/20 transition-colors focus-within:border-violet-400/70">
            <textarea
              ref={textareaRef}
              id="chat-input"
              aria-label="Message StudyMate"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message StudyMate…"
              rows={1}
              disabled={isSending}
              className="block w-full resize-none bg-transparent px-2 py-1 text-sm text-white outline-none placeholder:text-slate-500 disabled:cursor-not-allowed disabled:opacity-60"
              style={{ minHeight: '40px', maxHeight: '180px' }}
            />
            <div className="mt-2 flex items-center justify-between border-t border-slate-800 pt-3">
              <span className="text-xs text-slate-500">Enter to send · Shift + Enter for new line</span>
              <button
                id="send-message-btn"
                type="button"
                onClick={() => void sendMessage()}
                disabled={!draft.trim() || isSending}
                className="rounded-lg bg-gradient-to-r from-violet-500 to-purple-600 px-4 py-1.5 text-xs font-semibold text-white shadow transition hover:from-violet-400 hover:to-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSending ? 'Sending…' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default ChatWindow
