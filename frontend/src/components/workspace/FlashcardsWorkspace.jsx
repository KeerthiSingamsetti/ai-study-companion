import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence, useMotionValue, useTransform } from 'framer-motion'
import confetti from 'canvas-confetti'
import { generateFlashcards } from '../../lib/flashcardsApi'
import { reportFlashcardResult } from '../../lib/progressApi'
import IndexTab from '../common/IndexTab'
import FlashcardsSetupForm from './FlashcardsSetupForm'

/* ── Icons ──────────────────────────────────────────────── */
function ChevronLeftIcon() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

function FlipIcon() {
  return (
    <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 0 0 4.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 0 1-15.357-2m15.357 2H15" />
    </svg>
  )
}

function ClockIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  )
}

function RefreshCwIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 0 0 4.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 0 1-15.357-2m15.357 2H15" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  )
}

function SparklesIcon() {
  return (
    <svg className="size-3.5 text-amber-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  )
}

/* ── Circular Progress Ring Component ───────────────────────────── */
function CircularProgress({ value = 0, size = 48, strokeWidth = 4 }) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (value / 100) * circumference

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255, 255, 255, 0.08)"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="url(#gradientRing)"
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
        />
        <defs>
          <linearGradient id="gradientRing" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#8B5CF6" />
            <stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
        </defs>
      </svg>
      <span className="absolute font-mono-numbers text-[11px] font-bold text-white">
        {Math.round(value)}%
      </span>
    </div>
  )
}

/* ── Main FlashcardsWorkspace Component ─────────────────────────── */
export default function FlashcardsWorkspace({
  flashcardData,
  flashcardPrefill,
  onFlashcardsUpdate,
  documents = [],
  threadId,
}) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState('')
  const [showSetupForm, setShowSetupForm] = useState(false)
  const [localDeck, setLocalDeck] = useState(flashcardData)

  // Gamification stats
  const [xp, setXp] = useState(150)
  const [cardRatings, setCardRatings] = useState({})
  const [direction, setDirection] = useState(0) // -1 for left, 1 for right

  // Mouse Parallax Motion Values
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const rotateX = useTransform(y, [-100, 100], [8, -8])
  const rotateY = useTransform(x, [-100, 100], [-8, 8])

  function handleMouseMove(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    x.set(event.clientX - centerX)
    y.set(event.clientY - centerY)
  }

  function handleMouseLeave() {
    x.set(0)
    y.set(0)
  }

  useEffect(() => {
    if (flashcardData) {
      setLocalDeck(flashcardData)
      setCardRatings({})
      setCurrentIndex(0)
      setIsFlipped(false)
    }
  }, [flashcardData])

  const activeDeck = localDeck || flashcardData
  const cards = Array.isArray(activeDeck?.cards)
    ? activeDeck.cards
    : Array.isArray(activeDeck?.flashcards)
    ? activeDeck.flashcards
    : []
  const hasCards = cards.length > 0
  const currentCard = cards[currentIndex] ?? cards[0]

  // Calculate unique rating stats
  const gotItCount = Object.values(cardRatings).filter((r) => r === 'got_it').length
  const needReviewCount = Object.values(cardRatings).filter((r) => r === 'need_review').length
  const stillLearningCount = Object.values(cardRatings).filter((r) => r === 'still_learning').length
  const totalRated = Object.keys(cardRatings).length
  const completionPercentage = hasCards ? (totalRated / cards.length) * 100 : 0

  // Trigger confetti when deck is fully completed
  useEffect(() => {
    if (hasCards && totalRated === cards.length && cards.length > 0) {
      confetti({
        particleCount: 80,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#8B5CF6', '#3B82F6', '#10B981'],
      })
    }
  }, [totalRated, hasCards, cards.length])

  const handleNext = useCallback(() => {
    if (!hasCards) return
    setDirection(1)
    setIsFlipped(false)
    setCurrentIndex((prev) => (prev + 1) % cards.length)
  }, [hasCards, cards.length])

  const handlePrev = useCallback(() => {
    if (!hasCards) return
    setDirection(-1)
    setIsFlipped(false)
    setCurrentIndex((prev) => (prev - 1 + cards.length) % cards.length)
  }, [hasCards, cards.length])

  const handleFlip = useCallback(() => {
    setIsFlipped((prev) => !prev)
  }, [])

  // Single card evaluation handler
  const handleRateCard = useCallback(
    (rating) => {
      if (!currentCard || !activeDeck) return

      const term = currentCard.term ?? currentCard.front ?? currentCard.question ?? ''
      const topic = activeDeck.topic ?? 'General Study'
      const isMastered = rating === 'got_it'

      if (isMastered && cardRatings[currentIndex] !== 'got_it') {
        setXp((prev) => prev + 50)
      }

      // Log progress to backend
      const docId = activeDeck?.document_id || (documents[0]?.id ?? '')
      const cardStatus = isMastered ? 'known' : 'learning'
      if (docId) {
        void reportFlashcardResult(docId, topic, [{ front: term, status: cardStatus }]).catch(() => {})
      }

      setCardRatings((prev) => ({
        ...prev,
        [currentIndex]: rating,
      }))

      setIsFlipped(false)
      if (cards.length > 1) {
        setDirection(1)
        setCurrentIndex((prev) => (prev + 1) % cards.length)
      }
    },
    [currentCard, activeDeck, currentIndex, cards.length, cardRatings]
  )

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e) {
      if (showSetupForm || !hasCards) return
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        return
      }

      if (e.key === 'ArrowRight') {
        e.preventDefault()
        handleNext()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        handlePrev()
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault()
        handleFlip()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showSetupForm, hasCards, handleNext, handlePrev, handleFlip])

  async function handleGenerateForm({ documentId, topic, numCards }) {
    setIsGenerating(true)
    setError('')
    try {
      const result = await generateFlashcards(documentId, topic, numCards)
      setLocalDeck(result)
      setCardRatings({})
      setCurrentIndex(0)
      setIsFlipped(false)
      setShowSetupForm(false)
      if (onFlashcardsUpdate) onFlashcardsUpdate(result)
    } catch (err) {
      setError(err.message || 'Failed to generate flashcards.')
    } finally {
      setIsGenerating(false)
    }
  }

  // Setup Form View
  if (!activeDeck || !hasCards || showSetupForm) {
    return (
      <div className="space-y-4 max-w-xl mx-auto p-4 animate-fade-in font-sans">
        {showSetupForm && activeDeck && (
          <button
            type="button"
            onClick={() => setShowSetupForm(false)}
            className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-white transition-colors mb-2"
          >
            <ChevronLeftIcon />
            <span>Back to current deck</span>
          </button>
        )}

        {error && (
          <p className="rounded-2xl border border-[var(--danger)]/30 bg-[var(--danger-soft)] p-3 text-xs text-[var(--danger)]">
            {error}
          </p>
        )}

        <FlashcardsSetupForm
          documents={documents}
          isGenerating={isGenerating}
          onSubmit={handleGenerateForm}
          flashcardPrefill={flashcardPrefill}
        />
      </div>
    )
  }

  const topicName = activeDeck.topic ?? 'Study Deck'
  const cardTag = currentCard?.tag ?? currentCard?.category ?? 'Concept'
  const termText = currentCard?.front ?? currentCard?.term ?? currentCard?.question ?? ''
  const definitionText = currentCard?.back ?? currentCard?.definition ?? currentCard?.answer ?? ''
  const difficulty = currentCard?.difficulty ?? activeDeck.difficulty ?? 'medium'
  const exampleText = currentCard?.example ?? currentCard?.examples ?? null
  const hintText = currentCard?.hint ?? currentCard?.memory_trick ?? null
  const formulaText = currentCard?.formula ?? null

  return (
    <div className="flex flex-col items-center gap-6 p-6 max-w-3xl mx-auto animate-fade-in text-[var(--text-primary)] font-sans">
      {/* ── Gamification Header Bar ───────────────────────────────── */}
      <div className="w-full max-w-[520px] rounded-3xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CircularProgress value={completionPercentage} size={44} strokeWidth={4} />
            <div>
              <h2 className="text-base font-bold text-white capitalize truncate max-w-[200px]">
                {topicName}
              </h2>
              <p className="text-[11px] text-[var(--text-muted)] font-medium">
                {totalRated} of {cards.length} cards reviewed
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* XP Badge */}
            <span className="flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-mono-numbers font-bold text-amber-300">
              ⚡ {xp} XP
            </span>
            {/* Streak Badge */}
            <span className="hidden sm:flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-mono-numbers font-bold text-violet-300">
              🔥 3 Day Streak
            </span>
            <button
              type="button"
              onClick={() => setShowSetupForm(true)}
              className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:border-white/20 hover:text-white transition"
              title="New Flashcard Deck"
            >
              <PlusIcon />
              <span>New</span>
            </button>
          </div>
        </div>
      </div>

      {/* ── Flanking Buttons & Interactive 3D Card ─────────────────── */}
      <div className="flex items-center justify-center gap-4 w-full">
        {/* Prev Button */}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          type="button"
          onClick={handlePrev}
          className="grid size-11 place-items-center rounded-full border border-white/10 bg-white/[0.04] text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:bg-white/[0.08] hover:text-white shrink-0 focus-visible shadow-lg"
          aria-label="Previous card"
        >
          <ChevronLeftIcon />
        </motion.button>

        {/* Card Motion Slide Container */}
        <div className="w-full max-w-[520px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentIndex}
              initial={{ opacity: 0, x: direction * 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: direction * -40 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="w-full"
            >
              {/* 3D Flip Card Outer Container */}
              <div
                className={`flip-outer ${isFlipped ? 'flipped' : ''}`}
                onClick={handleFlip}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleFlip()}
              >
                <div className="flip-inner">
                  {/* ── Front Face ──────────────────────────────────────── */}
                  <div className="face flex flex-col justify-between p-6">
                    <div className="flex items-center justify-between gap-2 border-b border-white/5 pb-3">
                      <IndexTab variant="accent">{cardTag}</IndexTab>
                      <span className="text-[10px] font-mono-numbers font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full border border-white/10 bg-white/5 text-[var(--text-secondary)]">
                        {difficulty}
                      </span>
                    </div>


                    <div className="my-auto py-4 space-y-3 text-center">
                      <p className="text-xl font-bold leading-relaxed text-white tracking-tight">
                        {termText}
                      </p>
                      {exampleText && (
                        <p className="text-xs text-[var(--text-secondary)] italic max-w-md mx-auto">
                          e.g. {exampleText}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center justify-center gap-1.5 text-xs text-[var(--text-muted)] pt-3 border-t border-white/5">
                      <FlipIcon />
                      <span>Tap to reveal answer</span>
                    </div>
                  </div>

                  {/* ── Back Face ───────────────────────────────────────── */}
                  <div className="face face-back flex flex-col justify-between p-6">
                    <div className="flex items-center justify-between gap-2 border-b border-white/5 pb-3">
                      <IndexTab variant="warning">Detailed Answer</IndexTab>
                      <span className="font-mono-numbers text-xs text-[var(--accent)] font-semibold">
                        Card {currentIndex + 1}/{cards.length}
                      </span>
                    </div>

                    <div className="my-auto py-3 overflow-y-auto max-h-[200px] space-y-3 pr-1">
                      <p className="text-sm leading-relaxed text-[var(--text-primary)]">
                        {definitionText}
                      </p>
                      {formulaText && (
                        <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-2.5 text-xs font-mono-numbers text-blue-300">
                          Formula: {formulaText}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-center gap-1.5 text-xs text-[var(--text-muted)] pt-3 border-t border-white/5">
                      <FlipIcon />
                      <span>Tap to flip back</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Next Button */}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          type="button"
          onClick={handleNext}
          className="grid size-11 place-items-center rounded-full border border-white/10 bg-white/[0.04] text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:bg-white/[0.08] hover:text-white shrink-0 focus-visible shadow-lg"
          aria-label="Next card"
        >
          <ChevronRightIcon />
        </motion.button>
      </div>

      {/* ── 3 Interactive Recall Action Buttons ───────────────────── */}
      <div className="grid grid-cols-3 gap-3 w-full max-w-[520px]">
        <motion.button
          whileHover={{ scale: 1.03, y: -1 }}
          whileTap={{ scale: 0.96 }}
          type="button"
          onClick={() => handleRateCard('still_learning')}
          className={`flex items-center justify-center gap-1.5 rounded-2xl border px-3 py-3 text-xs font-bold transition-all shadow-md focus-visible ${
            cardRatings[currentIndex] === 'still_learning'
              ? 'border-[var(--warning)] bg-[var(--warning-soft)] text-[var(--warning)] ring-2 ring-[var(--warning)]/50'
              : 'border-[var(--warning)]/30 bg-[#141420] text-[var(--warning)] hover:bg-[var(--warning-soft)]'
          }`}
        >
          <ClockIcon />
          <span>Still Learning</span>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.03, y: -1 }}
          whileTap={{ scale: 0.96 }}
          type="button"
          onClick={() => handleRateCard('need_review')}
          className={`flex items-center justify-center gap-1.5 rounded-2xl border px-3 py-3 text-xs font-bold transition-all shadow-md focus-visible ${
            cardRatings[currentIndex] === 'need_review'
              ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)] ring-2 ring-[var(--accent)]/50'
              : 'border-[var(--accent)]/30 bg-[#141420] text-[var(--accent)] hover:bg-[var(--accent-soft)]'
          }`}
        >
          <RefreshCwIcon />
          <span>Need Review</span>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.03, y: -1 }}
          whileTap={{ scale: 0.96 }}
          type="button"
          onClick={() => handleRateCard('got_it')}
          className={`flex items-center justify-center gap-1.5 rounded-2xl border px-3 py-3 text-xs font-bold transition-all shadow-md focus-visible ${
            cardRatings[currentIndex] === 'got_it'
              ? 'border-[var(--success)] bg-[var(--success-soft)] text-[var(--success)] ring-2 ring-[var(--success)]/50'
              : 'border-[var(--success)]/30 bg-[#141420] text-[var(--success)] hover:bg-[var(--success-soft)]'
          }`}
        >
          <CheckIcon />
          <span>Got It</span>
        </motion.button>
      </div>

      {/* ── Footer Stats ──────────────────────────────────────────── */}
      <div className="flex items-center justify-center gap-6 text-xs text-[var(--text-muted)] font-mono-numbers">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[var(--success)]" />
          <span>{gotItCount} Mastered</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[var(--accent)]" />
          <span>{needReviewCount} Need Review</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[var(--warning)]" />
          <span>{stillLearningCount} Still Learning</span>
        </span>
      </div>
    </div>
  )
}
