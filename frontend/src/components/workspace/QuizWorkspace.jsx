import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { regenerateQuiz } from '../../lib/quizApi'
import { reportQuizResult } from '../../lib/progressApi'
import IndexTab from '../common/IndexTab'
import QuizSetupForm from './QuizSetupForm'

/* ── SVG Icons ────────────────────────────────────────── */
function RefreshIcon({ className = 'size-3.5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 0 0 4.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 0 1-15.357-2m15.357 2H15" />
    </svg>
  )
}

function ChevronLeftIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

function PlusIcon({ className = 'size-3.5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="size-4 text-[var(--success)] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg className="size-4 text-[var(--danger)] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function DocumentIcon() {
  return (
    <svg className="size-3.5 text-[var(--accent)] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
    </svg>
  )
}

/* ── Main QuizWorkspace Component ──────────────────────── */
export default function QuizWorkspace({
  quizData,
  onQuizUpdate,
  documents = [],
  isExpanded = false,
  onToggleExpand,
  quizPrefill,
}) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [userAnswers, setUserAnswers] = useState({})
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState('')
  const [showSetupForm, setShowSetupForm] = useState(false)
  const [localQuizData, setLocalQuizData] = useState(quizData)
  const [shakingIdx, setShakingIdx] = useState(null)

  const [reportedQuizData, setReportedQuizData] = useState(quizData)
  const hasReportedRef = useRef(false)

  useEffect(() => {
    if (quizData) setLocalQuizData(quizData)
  }, [quizData])

  useEffect(() => {
    if (quizPrefill) {
      setLocalQuizData(null)
      setShowSetupForm(false)
    }
  }, [quizPrefill])



  const activeQuiz = localQuizData || quizData
  const questions = Array.isArray(activeQuiz?.questions) ? activeQuiz.questions : []
  const hasQuestions = questions.length > 0
  const answeredCount = Object.keys(userAnswers).length

  useEffect(() => {
    setUserAnswers({})
    setCurrentIndex(0)
    hasReportedRef.current = false
    setReportedQuizData(activeQuiz)
  }, [activeQuiz])

  // Automatically report quiz score once all questions are answered
  useEffect(() => {
    if (
      !activeQuiz ||
      reportedQuizData !== activeQuiz ||
      !hasQuestions ||
      answeredCount !== questions.length ||
      hasReportedRef.current
    ) return

    hasReportedRef.current = true
    void reportQuizResult(
      activeQuiz.document_id,
      activeQuiz.topic,
      questions.map((question, index) => ({
        question: question.question,
        correct: userAnswers[index] === question.correct_index,
      })),
    ).catch(() => {})
  }, [answeredCount, hasQuestions, questions, activeQuiz, reportedQuizData, userAnswers])

  async function handleGenerateForm({ documentId, topic, numQuestions, difficulty }) {
    setIsGenerating(true)
    setError('')
    try {
      const result = await regenerateQuiz(documentId, topic, numQuestions, difficulty)
      setLocalQuizData(result)
      setUserAnswers({})
      setCurrentIndex(0)
      hasReportedRef.current = false
      setShowSetupForm(false)
      if (onQuizUpdate) onQuizUpdate(result)
    } catch (err) {
      setError(err.message || 'Failed to generate quiz.')
    } finally {
      setIsGenerating(false)
    }
  }

  // Calculate score
  const correctCount = Object.entries(userAnswers).reduce((count, [qIdx, chosenIdx]) => {
    const question = questions[Number(qIdx)]
    return question && question.correct_index === chosenIdx ? count + 1 : count
  }, 0)

  function handleSelectOption(optionIndex) {
    if (userAnswers[currentIndex] !== undefined) return
    const currentQ = questions[currentIndex]
    if (currentQ && optionIndex !== currentQ.correct_index) {
      setShakingIdx(optionIndex)
      setTimeout(() => setShakingIdx(null), 500)
    }
    setUserAnswers((prev) => ({
      ...prev,
      [currentIndex]: optionIndex,
    }))
  }

  async function handleRegenerate() {
    if (isGenerating || !activeQuiz) return
    setIsGenerating(true)
    setError('')
    try {
      const refreshed = await regenerateQuiz(
        activeQuiz.document_id,
        activeQuiz.topic,
        questions.length,
        activeQuiz.difficulty ?? 'medium'
      )
      setLocalQuizData(refreshed)
      setUserAnswers({})
      hasReportedRef.current = false
      setCurrentIndex(0)
      if (onQuizUpdate) onQuizUpdate(refreshed)
    } catch (err) {
      setError(err.message || 'Failed to regenerate quiz.')
    } finally {
      setIsGenerating(false)
    }
  }

  const currentQuestion = questions[currentIndex] ?? questions[0]
  const selectedAnswer = userAnswers[currentIndex]
  const isAnswered = selectedAnswer !== undefined
  const optionLabels = ['A', 'B', 'C', 'D', 'E', 'F']

  // Keyboard navigation & option selection
  useEffect(() => {
    function handleKeyDown(e) {
      if (showSetupForm || !hasQuestions) return
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        return
      }

      if (!isAnswered && currentQuestion?.options) {
        const optionCount = currentQuestion.options.length
        if (e.key >= '1' && e.key <= String(optionCount)) {
          handleSelectOption(Number(e.key) - 1)
          return
        }
        const lower = e.key.toLowerCase()
        const keys = ['a', 'b', 'c', 'd', 'e', 'f']
        const idx = keys.indexOf(lower)
        if (idx !== -1 && idx < optionCount) {
          handleSelectOption(idx)
          return
        }
      }

      if (isAnswered && e.key === 'Enter') {
        e.preventDefault()
        if (currentIndex < questions.length - 1) {
          setCurrentIndex((prev) => prev + 1)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showSetupForm, hasQuestions, isAnswered, currentIndex, questions.length, currentQuestion])

  // Setup Form View
  if (!activeQuiz || !hasQuestions || showSetupForm) {
    return (
      <div className="space-y-4 max-w-xl mx-auto p-4 animate-fade-in font-sans">
        {showSetupForm && activeQuiz && (
          <button
            type="button"
            onClick={() => setShowSetupForm(false)}
            className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-white transition-colors mb-2"
          >
            <ChevronLeftIcon />
            <span>Back to current quiz</span>
          </button>
        )}

        {error && (
          <p className="rounded-2xl border border-[var(--danger)]/30 bg-[var(--danger-soft)] p-3 text-xs text-[var(--danger)]">
            {error}
          </p>
        )}

        <QuizSetupForm
          documents={documents}
          isGenerating={isGenerating}
          onSubmit={handleGenerateForm}
          quizPrefill={quizPrefill}
        />
      </div>
    )
  }

  // Document provenance name
  const docObj = documents.find((d) => d.id === activeQuiz?.document_id)
  const docName = docObj?.filename ?? activeQuiz?.document_name ?? (activeQuiz?.document_id ? `Doc: ${activeQuiz.document_id}` : 'Uploaded Document')
  const citationText = currentQuestion?.source_citation ?? docName

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl mx-auto animate-fade-in text-[var(--text-primary)] font-sans">
      {/* ── Header Toolbar & Score Tally ────────────────────────────── */}
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl shadow-xl space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <IndexTab variant="accent">{activeQuiz?.topic ?? 'Practice Quiz'}</IndexTab>
              <span className="text-[10px] font-mono-numbers text-[var(--text-muted)] uppercase tracking-wider">
                {activeQuiz?.difficulty ?? 'medium'}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              📄 {docName}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Running Score Tally */}
            <div className="font-mono-numbers text-xs font-bold text-[var(--success)] bg-[var(--success-soft)] px-3 py-1.5 rounded-full border border-[var(--success)]/30">
              {correctCount} / {questions.length} correct
            </div>

            <button
              type="button"
              onClick={() => void handleRegenerate()}
              disabled={isGenerating}
              className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-white/20 hover:text-white disabled:opacity-50"
              title="Regenerate Quiz"
            >
              <RefreshIcon className={`size-3.5 ${isGenerating ? 'animate-spin text-[var(--accent)]' : ''}`} />
              <span>{isGenerating ? 'Generating…' : 'Regenerate'}</span>
            </button>

            <button
              type="button"
              onClick={() => setShowSetupForm(true)}
              className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-white/20 hover:text-white"
              title="New Quiz"
            >
              <PlusIcon />
              <span>New</span>
            </button>
          </div>
        </div>

        {/* Progress Bar Track */}
        <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-violet-600 to-indigo-500"
            initial={{ width: 0 }}
            animate={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      {/* ── Question Card ─────────────────────────────────────────── */}
      <motion.div
        key={currentIndex}
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl shadow-2xl space-y-6"
      >
        {/* Question Header */}
        <div className="space-y-2">
          <span className="font-mono-numbers text-xs font-bold text-[var(--accent)]">
            Question {currentIndex + 1} of {questions.length}
          </span>
          <h3 className="text-lg font-bold leading-relaxed text-white">
            {currentQuestion?.question}
          </h3>
        </div>

        {/* ── Full-Width Option Rows with Shake & Check Animations ─── */}
        <div className="space-y-3">
          {currentQuestion?.options?.map((option, idx) => {
            const isSelected = selectedAnswer === idx
            const isCorrect = currentQuestion.correct_index === idx
            const isShaking = shakingIdx === idx

            let rowStyle = 'border-white/10 bg-white/[0.02] text-[var(--text-primary)] hover:border-white/20 hover:bg-white/[0.05]'

            if (isAnswered) {
              if (isCorrect) {
                rowStyle = 'border-[var(--success)] bg-[var(--success-soft)] text-[var(--success)] font-semibold shadow-lg shadow-emerald-500/10'
              } else if (isSelected && !isCorrect) {
                rowStyle = 'border-[var(--danger)] bg-[var(--danger-soft)] text-[var(--danger)] font-semibold shadow-lg shadow-rose-500/10'
              } else {
                rowStyle = 'border-white/5 bg-transparent opacity-40 pointer-events-none'
              }
            }

            return (
              <motion.button
                key={idx}
                type="button"
                disabled={isAnswered}
                whileHover={!isAnswered ? { scale: 1.01, x: 2 } : {}}
                whileTap={!isAnswered ? { scale: 0.99 } : {}}
                animate={isShaking ? { x: [-10, 10, -8, 8, -4, 4, 0] } : {}}
                transition={{ duration: 0.4 }}
                onClick={() => handleSelectOption(idx)}
                className={`w-full flex items-center justify-between gap-4 rounded-2xl border p-4 text-left text-xs transition-all focus-visible ${rowStyle}`}
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <span
                    className={`grid size-7 shrink-0 place-items-center rounded-xl font-mono-numbers text-xs font-bold transition-all ${
                      isAnswered && isCorrect
                        ? 'bg-[var(--success)] text-slate-950 shadow-md'
                        : isAnswered && isSelected && !isCorrect
                        ? 'bg-[var(--danger)] text-white shadow-md'
                        : 'bg-white/5 border border-white/10 text-[var(--text-secondary)]'
                    }`}
                  >
                    {optionLabels[idx] ?? idx + 1}
                  </span>
                  <span className="leading-relaxed">{option}</span>
                </div>

                {/* Status Icon Slot */}
                {isAnswered && (
                  <div className="shrink-0 pl-2">
                    {isCorrect ? (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }}>
                        <CheckIcon />
                      </motion.div>
                    ) : isSelected ? (
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                        <XIcon />
                      </motion.div>
                    ) : null}
                  </div>
                )}
              </motion.button>
            )
          })}
        </div>

        {/* ── Animated Explanation & PDF Citation Panel ────────────── */}
        <AnimatePresence>
          {isAnswered && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-4.5 space-y-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-white">
                  {selectedAnswer === currentQuestion.correct_index ? '✓ Correct Answer' : '✕ Explanation'}
                </span>

                {/* Source PDF Citation Chip */}
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1 text-[11px] font-mono-numbers text-[var(--accent)] font-semibold">
                  <DocumentIcon />
                  <span>{citationText}</span>
                </span>
              </div>

              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {currentQuestion?.explanation || 'No explanation provided.'}
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Next Question Button / Pagination Footer ────────────── */}
        <div className="flex items-center justify-between pt-3 border-t border-white/5">
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={currentIndex === 0}
              onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
              className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-white disabled:opacity-30"
            >
              <ChevronLeftIcon />
              <span>Prev</span>
            </button>

            <button
              type="button"
              disabled={currentIndex === questions.length - 1}
              onClick={() => setCurrentIndex((prev) => Math.min(questions.length - 1, prev + 1))}
              className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-white disabled:opacity-30"
            >
              <span>Next</span>
              <ChevronRightIcon />
            </button>
          </div>

          {/* Sliding Next Question Button once answered */}
          {isAnswered && currentIndex < questions.length - 1 && (
            <motion.button
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={() => setCurrentIndex((prev) => prev + 1)}
              className="flex-1 ml-4 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-lg shadow-violet-600/30 transition-all focus-visible"
            >
              Next Question →
            </motion.button>
          )}
        </div>
      </motion.div>
    </div>
  )
}
