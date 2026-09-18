import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Send, Sparkles, Target, BookOpen } from 'lucide-react'
import { getProjectAnalytics, getThreadMessages } from '../api/client'
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

/**
 * Pick the concept with the lowest mastery score for proactive session opening.
 * Returns null when the project has no mastery evidence yet.
 */
function pickWeakestConcept(mastery = []) {
  const scored = mastery.filter((row) => typeof row?.score === 'number')
  if (scored.length === 0) return null
  return scored.reduce((weakest, row) => (row.score < weakest.score ? row : weakest))
}

/* ── Typing indicator dots ──────────────────────────────── */
function TypingDots() {
  return (
    <span className="flex items-center gap-1" aria-label="AI Study Companion is responding">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="block size-1.5 rounded-full bg-[var(--accent)]/70"
          style={{ animation: `bounce-dot 1s ${delay}ms infinite ease-in-out` }}
        />
      ))}
    </span>
  )
}

/* ── Assistant avatar ───────────────────────────────────── */
function TutorAvatar() {
  return (
    <div className="grid size-8 shrink-0 place-items-center rounded-xl border border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/30 to-transparent text-[var(--accent)]">
      <Sparkles className="size-3.5" />
    </div>
  )
}

/* ── Generic assistant-response indicator ───────────────── */
function ThinkingIndicator() {
  return (
    <div className="flex animate-fade-in items-center gap-3 text-sm text-[var(--text-secondary)]">
      <TutorAvatar />
      <div className="flex items-center gap-2.5 rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] px-4 py-3 text-xs text-[var(--text-secondary)]">
        <span className="relative flex size-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent)] opacity-75" />
          <span className="relative inline-flex size-2 rounded-full bg-[var(--accent)]" />
        </span>
        <span className="font-medium">Thinking…</span>
        <TypingDots />
      </div>
    </div>
  )
}

/* ── Skeleton Message ───────────────────────────────────── */
function HistorySkeleton() {
  return (
    <div className="animate-fade-in space-y-4 py-4">
      <div className="flex justify-end gap-3">
        <div className="skeleton h-10 w-2/3 rounded-2xl" />
      </div>
      <div className="flex justify-start gap-3">
        <div className="skeleton size-8 rounded-xl" />
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
  const [sessionOpener, setSessionOpener] = useState(null)
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

  /* Proactive session opening: reference the weakest concept when reopening a project */
  useEffect(() => {
    if (activeWorkspace && activeWorkspace !== 'chat') return
    if (!threadId || threadId === 'undefined') {
      setSessionOpener(null)
      return
    }

    let isCurrent = true
    getProjectAnalytics(threadId)
      .then((data) => {
        if (!isCurrent) return
        const weakest = pickWeakestConcept(data?.mastery)
        setSessionOpener(
          weakest
            ? {
                concept: weakest.concept,
                score: Math.round(weakest.score),
                attempts: weakest.attempts ?? 0,
              }
            : null,
        )
      })
      .catch(() => {
        if (isCurrent) setSessionOpener(null)
      })

    return () => {
      isCurrent = false
    }
  }, [threadId, activeWorkspace])

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
      {/* ── Scrollable message list ─────────────── */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col px-5 py-10">
          {isLoadingHistory ? (
            <HistorySkeleton />
          ) : messages.length === 0 ? (
            /* Empty state */
            <div className="my-auto animate-fade-in py-12">
              <span className="inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent)]">
                <Sparkles className="size-3.5" /> AI Tutor
              </span>
              <h1 className="mt-4 font-display text-3xl font-bold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                What would you like to learn today?
              </h1>
              <p className="mt-4 max-w-xl text-base leading-7 text-[var(--text-secondary)]">
                Ask a question grounded in your own course material. Answers cite the exact document and page,
                and tell you honestly when the evidence is not there.
              </p>

              {sessionOpener && (
                <div className="mt-6 max-w-xl rounded-2xl border border-[var(--accent)]/25 bg-gradient-to-br from-[var(--accent-soft)] to-transparent px-4 py-3.5 text-sm text-[var(--text-primary)]">
                  <span className="font-semibold text-[var(--accent)]">Welcome back.</span> Your weakest concept in
                  this project is <span className="font-semibold">{sessionOpener.concept}</span> (mastery{' '}
                  {sessionOpener.score}%
                  {sessionOpener.attempts ? `, ${sessionOpener.attempts} attempt(s)` : ''}). Want to review it before
                  moving on?
                  <button
                    type="button"
                    onClick={() => onQuizTopic?.(sessionOpener.concept)}
                    className="mt-2.5 flex items-center gap-1.5 rounded-xl border border-[var(--accent)]/40 bg-[var(--accent)] px-3 py-1.5 text-xs font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)]"
                  >
                    <Target className="size-3.5" /> Practise this concept
                  </button>
                </div>
              )}

              <div className="mt-8 flex flex-wrap gap-2">
                {[
                  { label: 'Explain this concept simply', icon: BookOpen },
                  { label: 'Quiz me on this topic', icon: Target },
                  { label: 'Give me study tips', icon: Sparkles },
                ].map((suggestion) => (
                  <button
                    key={suggestion.label}
                    type="button"
                    onClick={() => {
                      setDraft(suggestion.label)
                      textareaRef.current?.focus()
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
                  >
                    <suggestion.icon className="size-3.5 text-[var(--accent)]" />
                    {suggestion.label}
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
                    className={`flex animate-fade-in gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {message.role === 'assistant' && <TutorAvatar />}
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                        message.role === 'user'
                          ? 'border border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[var(--text-primary)]'
                          : 'glass-card text-[var(--text-secondary)]'
                      }`}
                    >
                      {message.role === 'assistant' ? (
                        <>
                          {/* 1. Header text / markdown message */}
                          {(() => {
                            const { body, parsedSources } = parseBodyAndSources(message.content)
                            return (
                              <>
                                <MarkdownMessage content={body} />

                                {/* 2. Weak topics card */}
                                {activeProgressData && (
                                  <WeakTopicsCard
                                    progressData={activeProgressData}
                                    onOpenProgressTab={onOpenProgressTab}
                                  />
                                )}

                                {message.toolStatus && (
                                  <div className="mt-3 border-t border-[var(--border)] pt-2">
                                    <ToolStatusIndicator
                                      message={message.toolStatus.message}
                                      detail={message.toolStatus.detail}
                                    />
                                  </div>
                                )}

                                <CitationBadges sources={message.sources ?? []} parsedSources={parsedSources} />
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

      {/* ── Composer ──────────────────────────────── */}
      <div className="shrink-0 border-t border-[var(--border)] bg-[var(--bg)]/80 px-5 py-4 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl">
          {error && (
            <p role="alert" className="mb-2 rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          )}
          <div className="glass-card rounded-2xl p-3 transition-colors focus-within:border-[var(--accent)]/50">
            <textarea
              ref={textareaRef}
              id="chat-input"
              aria-label="Message AI Study Companion"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message your AI Tutor…"
              rows={1}
              disabled={isSending}
              className="block w-full resize-none bg-transparent px-2 py-1 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
              style={{ minHeight: '40px', maxHeight: '180px' }}
            />
            <div className="mt-2 flex items-center justify-between border-t border-[var(--border)] pt-3">
              <span className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                <MessageSquare className="size-3.5" />
                Enter to send · Shift + Enter for a new line
              </span>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                id="send-message-btn"
                type="button"
                onClick={() => void sendMessage()}
                disabled={!draft.trim() || isSending}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-1.5 text-xs font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="size-3.5" />
                {isSending ? 'Sending…' : 'Send'}
              </motion.button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default ChatWindow
