import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

/* ── SVG Icons ────────────────────────────────────────── */
function QuizSparklesIcon() {
  return (
    <svg className="size-7 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M18.25 7.5l.406 1.423a2.25 2.25 0 0 0 1.546 1.546L21.625 10.875l-1.423.406a2.25 2.25 0 0 0-1.546 1.546L18.25 14.25l-.406-1.423a2.25 2.25 0 0 0-1.546-1.546L14.875 10.875l1.423-.406a2.25 2.25 0 0 0 1.546-1.546L18.25 7.5z" />
    </svg>
  )
}

function BookOpenIcon() {
  return (
    <svg className="size-5 text-[var(--accent)] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  )
}

function MinusIcon() {
  return (
    <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
    </svg>
  )
}

function PlayIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  )
}

/* ── QuizSetupForm Component ───────────────────────────── */
export default function QuizSetupForm({ documents = [], isGenerating = false, onSubmit, quizPrefill }) {
  const [topic, setTopic] = useState(quizPrefill?.topic ?? '')
  const [difficulty, setDifficulty] = useState(quizPrefill?.difficulty ?? 'medium')
  const [numQuestions, setNumQuestions] = useState(quizPrefill?.numQuestions ?? 10)
  const [selectedDocId, setSelectedDocId] = useState(quizPrefill?.documentId ?? '')
  const [isCustomizing, setIsCustomizing] = useState(false)

  const isFromStudyProgress = Boolean(quizPrefill?.topic)

  // Update form fields when quizPrefill prop changes
  useEffect(() => {
    if (!quizPrefill) return
    setIsCustomizing(false)

    setTopic(quizPrefill.topic ?? '')
    setDifficulty(quizPrefill.difficulty ?? 'medium')
    setNumQuestions(quizPrefill.numQuestions ?? 10)
    if (quizPrefill.documentId) {
      setSelectedDocId(quizPrefill.documentId)
    }
  }, [quizPrefill])

  // Keep selectedDocId aligned with available documents without overwriting explicit prefill
  useEffect(() => {
    if (documents.length === 0) return

    // If we have a prefilled documentId and it exists in documents, keep it
    if (quizPrefill?.documentId && documents.some((d) => d.id === quizPrefill.documentId)) {
      if (selectedDocId !== quizPrefill.documentId) {
        setSelectedDocId(quizPrefill.documentId)
      }
      return
    }

    // Otherwise, if current selectedDocId is invalid or empty, set a fallback
    if (!selectedDocId || (selectedDocId !== 'all' && !documents.some((d) => d.id === selectedDocId))) {
      setSelectedDocId(documents.length > 1 ? 'all' : documents[0].id)
    }
  }, [documents, quizPrefill, selectedDocId])

  const effectiveDocId = selectedDocId || (documents.length > 1 ? 'all' : (documents[0]?.id ?? ''))
  const hasDocuments = documents.length > 0
  const isDocumentMissing = Boolean(quizPrefill?.documentId) && !documents.some((d) => d.id === quizPrefill.documentId)

  // Find document name for banner
  const matchedDoc = documents.find((d) => d.id === effectiveDocId)
  const sourceDocName = matchedDoc?.filename ?? quizPrefill?.documentName ?? (effectiveDocId === 'all' ? `All ${documents.length} Combined PDFs` : 'Uploaded Document')

  function handleSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    if (!topic.trim() || isGenerating || !hasDocuments) return
    const actualDocId = effectiveDocId === 'all' ? documents[0]?.id : effectiveDocId
    if (onSubmit) {
      onSubmit({
        documentId: actualDocId,
        topic: topic.trim(),
        numQuestions,
        difficulty,
      })
    }
  }

  const difficultyOptions = [
    { value: 'easy', label: 'Easy' },
    { value: 'medium', label: 'Medium' },
    { value: 'hard', label: 'Hard' },
  ]

  // ── Weak Topic Context Banner View (From Progress) ─────────────────
  if (isFromStudyProgress && !isCustomizing) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex flex-col gap-5 max-w-xl mx-auto font-sans"
      >
        {/* Banner Card */}
        <div className="rounded-3xl border border-violet-500/30 bg-gradient-to-br from-[#131224] via-[#10101b] to-[#18152e] p-6 shadow-2xl space-y-5">
          <div className="flex items-start justify-between gap-3 border-b border-white/10 pb-4">
            <div className="flex items-center gap-3">
              <div className="grid size-12 place-items-center rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/30">
                <BookOpenIcon />
              </div>
              <div>
                <span className="text-[10px] font-mono-numbers font-bold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2.5 py-0.5 rounded-full border border-violet-500/20">
                  Topic Focused Quiz
                </span>
                <h2 className="text-lg font-bold text-white mt-1 leading-snug">
                  📚 Quiz based on your weak topic
                </h2>
              </div>
            </div>
          </div>

          {/* Focused Topic Highlight Card */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] block">
                Target Topic
              </span>
              <p className="text-base font-bold text-white mt-0.5">
                {topic}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5 text-xs text-[var(--text-secondary)] font-mono-numbers">
              <div>
                <span className="text-[var(--text-muted)]">Source: </span>
                <span className="font-semibold text-white">📄 {sourceDocName}</span>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full bg-white/5 border border-white/10 text-violet-300 font-semibold">
                  {numQuestions} Questions
                </span>
                <span className="px-2.5 py-0.5 rounded-full bg-white/5 border border-white/10 text-amber-300 font-semibold uppercase">
                  {difficulty}
                </span>
              </div>
            </div>
          </div>

          {/* Missing PDF Warning (If document was deleted) */}
          {isDocumentMissing && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-300 space-y-2">
              <p className="font-semibold">⚠️ This document is no longer available.</p>
              <button
                type="button"
                onClick={() => setIsCustomizing(true)}
                className="text-xs font-bold text-white underline hover:text-amber-200"
              >
                Choose another document →
              </button>
            </div>
          )}

          {/* Lightweight Multi-PDF Selector if multiple files exist */}
          {documents.length > 1 && (
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] block">
                We found this topic in multiple documents. Selected source:
              </span>
              <select
                value={effectiveDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#141420] px-3 py-2 text-xs text-white outline-none transition focus:border-violet-500"
              >
                <option value="all">📚 All Thread PDFs ({documents.length} Combined)</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    📄 {d.filename}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Single-Click Start Quiz Button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="button"
            disabled={!topic.trim() || !hasDocuments || isGenerating}
            onClick={handleSubmit}
            className="w-full flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 py-3.5 text-xs font-bold text-white shadow-xl shadow-violet-600/30 border border-white/20 transition hover:brightness-110 disabled:opacity-40"
          >
            {isGenerating ? (
              <span className="flex items-center gap-2">
                <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Generating Focused Quiz…
              </span>
            ) : (
              <>
                <PlayIcon />
                <span>Start Quiz</span>
              </>
            )}
          </motion.button>

          <div className="text-center pt-1">
            <button
              type="button"
              onClick={() => setIsCustomizing(true)}
              className="text-[11px] text-[var(--text-muted)] hover:text-white underline transition"
            >
              Customize difficulty or question count
            </button>
          </div>
        </div>
      </motion.div>
    )
  }

  // ── Standard Full Setup Form View ────────────────────────────────
  return (
    <div className="flex flex-col gap-5 animate-fade-in text-[var(--text-primary)] font-sans">
      {/* Header Banner */}
      <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl shadow-lg">
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-violet-500/15 border border-violet-400/30 text-violet-300">
          <QuizSparklesIcon />
        </div>
        <div>
          <h2 className="text-sm font-bold text-white">Generate Quiz</h2>
          <p className="text-xs text-[var(--text-muted)]">Build practice questions grounded directly in your uploaded PDFs</p>
        </div>
      </div>

      {/* Form Card */}
      <form onSubmit={handleSubmit} className="space-y-4 rounded-3xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl shadow-2xl">
        {/* Document Selection */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label htmlFor="quiz-document-select" className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Source Document ({documents.length} Uploaded)
            </label>
          </div>
          {!hasDocuments ? (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
              ⚠️ Please upload a PDF in the <strong>Documents</strong> tab first before generating a quiz.
            </div>
          ) : (
            <select
              id="quiz-document-select"
              value={effectiveDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-[#141420] px-3.5 py-2.5 text-xs text-white outline-none transition focus:border-[var(--accent)]"
            >
              {documents.length > 1 && (
                <option value="all">
                  📚 All Thread PDFs ({documents.length} Files Combined)
                </option>
              )}
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  📄 {doc.filename}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Topic Input */}
        <div>
          <label htmlFor="quiz-topic-input" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Topic / Subject <span className="text-violet-400">*</span>
          </label>
          <input
            id="quiz-topic-input"
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Linear Regression, Chapter 2, Photosynthesis"
            className="w-full rounded-xl border border-white/10 bg-[#141420] px-3.5 py-2.5 text-xs text-white placeholder:text-[var(--text-muted)] outline-none transition focus:border-[var(--accent)]"
          />
        </div>

        {/* Difficulty Pill Selection */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Difficulty Level
          </label>
          <div className="grid grid-cols-3 gap-2">
            {difficultyOptions.map((opt) => {
              const isSelected = difficulty === opt.value
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setDifficulty(opt.value)}
                  className={`rounded-xl border py-2 text-xs font-semibold transition ${
                    isSelected
                      ? 'border-violet-500 bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md'
                      : 'border-white/10 bg-white/5 text-[var(--text-muted)] hover:border-white/20 hover:text-white'
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Number of Questions Stepper */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Number of Questions
          </label>
          <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#141420] px-4 py-2">
            <span className="text-xs text-[var(--text-muted)] font-mono-numbers">Questions (3 - 20)</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setNumQuestions((prev) => Math.max(3, prev - 1))}
                disabled={numQuestions <= 3}
                className="grid size-7 place-items-center rounded-lg border border-white/10 bg-white/5 text-white transition hover:border-white/20 disabled:opacity-30"
                aria-label="Decrease question count"
              >
                <MinusIcon />
              </button>
              <span className="w-6 text-center font-mono-numbers text-sm font-bold text-violet-300">
                {numQuestions}
              </span>
              <button
                type="button"
                onClick={() => setNumQuestions((prev) => Math.min(20, prev + 1))}
                disabled={numQuestions >= 20}
                className="grid size-7 place-items-center rounded-lg border border-white/10 bg-white/5 text-white transition hover:border-white/20 disabled:opacity-30"
                aria-label="Increase question count"
              >
                <PlusIcon />
              </button>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!topic.trim() || !hasDocuments || isGenerating}
          className="mt-2 w-full rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 py-3 text-xs font-bold text-white shadow-lg shadow-violet-600/30 transition hover:brightness-110 disabled:opacity-40"
        >
          {isGenerating ? (
            <span className="flex items-center justify-center gap-2">
              <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Generating Quiz…
            </span>
          ) : (
            'Generate Quiz'
          )}
        </button>
      </form>
    </div>
  )
}
