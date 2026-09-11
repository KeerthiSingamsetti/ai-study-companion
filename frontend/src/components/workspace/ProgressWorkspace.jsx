import React, { useEffect, useState } from 'react'
import { Target, Trophy, Sparkles, ArrowRight, Activity, Brain } from 'lucide-react'
import { getStudyProgress } from '../../lib/progressApi'
import IndexTab from '../common/IndexTab'

/* ── CountUp Component for Stat Numbers ─────────────────── */
function CountUp({ end = 0, duration = 600 }) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let startTimestamp = null
    const endValue = Number(end) || 0

    function step(timestamp) {
      if (!startTimestamp) startTimestamp = timestamp
      const progress = Math.min((timestamp - startTimestamp) / duration, 1)
      setCount(Math.floor(progress * endValue))
      if (progress < 1) {
        window.requestAnimationFrame(step)
      } else {
        setCount(endValue)
      }
    }

    window.requestAnimationFrame(step)
  }, [end, duration])

  return <span className="font-mono-numbers">{count}</span>
}

/**
 * Redesigned full workspace panel for the "Progress" tab.
 * Uses design tokens, mono typography for stats, left-edge IndexTab motifs,
 * count-up animations, and subtle lift-on-hover card interactions.
 */
export default function ProgressWorkspace({ progressData, onUseTopic }) {
  const [localData, setLocalData] = useState(progressData)

  useEffect(() => {
    if (progressData) {
      setLocalData(progressData)
    } else {
      getStudyProgress()
        .then((data) => setLocalData(data))
        .catch(() => {})
    }
  }, [progressData])

  const activeData = progressData || localData
  const weakTopics = activeData?.weak_topics ?? []
  const quizAttempts = activeData?.quiz_attempts ?? []
  const studiedTopics = activeData?.studied_topics ?? []

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 text-[var(--text-primary)] font-sans max-w-4xl mx-auto animate-fade-in">
      {/* ── Workspace Header ────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)] border border-[var(--accent)]/30">
            <Activity className="size-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Study Performance & Progress
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Track focus areas, review quiz attempts, and strengthen weak topics
            </p>
          </div>
        </div>
      </div>

      {/* ── Summary KPI Bar with Animated Count-Up Numbers ─────────── */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-[var(--radius-card)] border border-[var(--warning)]/30 bg-[var(--warning-soft)] p-4 text-center space-y-1">
          <span className="block text-2xl font-extrabold text-[var(--warning)] font-mono-numbers">
            <CountUp end={weakTopics.length} />
          </span>
          <span className="text-[11px] font-semibold text-[var(--warning)] uppercase tracking-wider block">
            Weak Topics
          </span>
        </div>

        <div className="rounded-[var(--radius-card)] border border-[var(--success)]/30 bg-[var(--success-soft)] p-4 text-center space-y-1">
          <span className="block text-2xl font-extrabold text-[var(--success)] font-mono-numbers">
            <CountUp end={quizAttempts.length} />
          </span>
          <span className="text-[11px] font-semibold text-[var(--success)] uppercase tracking-wider block">
            Quizzes Completed
          </span>
        </div>

        <div className="rounded-[var(--radius-card)] border border-[var(--accent)]/30 bg-[var(--accent-soft)] p-4 text-center space-y-1">
          <span className="block text-2xl font-extrabold text-[var(--accent)] font-mono-numbers">
            <CountUp end={studiedTopics.length} />
          </span>
          <span className="text-[11px] font-semibold text-[var(--accent)] uppercase tracking-wider block">
            Topics Studied
          </span>
        </div>
      </div>

      {/* ── Focus Recommendations Section ───────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider flex items-center gap-2">
            <Target className="size-4 text-[var(--accent)]" />
            Focus Recommendations
          </h3>
          <span className="text-xs font-mono-numbers text-[var(--text-muted)]">
            {weakTopics.length} topic(s) tracked
          </span>
        </div>

        {weakTopics.length === 0 ? (
          <div className="rounded-[var(--radius-card)] border border-dashed border-[var(--border)] bg-[var(--surface-1)] p-8 text-center space-y-2">
            <Sparkles className="size-8 text-[var(--success)] mx-auto" />
            <h4 className="text-sm font-semibold text-[var(--text-primary)]">
              No weak topics tracked yet!
            </h4>
            <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
              Complete quizzes or study materials to automatically identify areas needing practice.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2">
            {weakTopics.map((item, idx) => {
              const isQuizReason = item.reason === 'quiz_score' || Boolean(item.formatted_score)

              return (
                <div
                  key={`${item.topic}-${idx}`}
                  className="group flex flex-col justify-between rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-4 transition-all duration-200 hover:-translate-y-[2px] hover:border-[var(--accent)]/50 hover:bg-[var(--surface-2)] shadow-sm"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-semibold text-sm text-[var(--text-primary)] group-hover:text-[var(--accent)] transition-colors">
                        {item.topic}
                      </h4>
                      <IndexTab
                        variant={isQuizReason ? 'warning' : 'accent'}
                        icon={isQuizReason ? Trophy : Brain}
                      >
                        {isQuizReason ? 'Low Quiz Score' : 'Flashcard Tag'}
                      </IndexTab>
                    </div>

                    <div className="text-xs text-[var(--text-muted)] font-mono-numbers">
                      {item.formatted_score ? (
                        <p className="flex items-center gap-1.5 font-medium text-[var(--warning)]">
                          <Trophy className="size-3 shrink-0 text-[var(--warning)]" />
                          <span>Score: {item.formatted_score}</span>
                          {item.date && <span className="text-[var(--text-muted)] font-normal"> • {item.date}</span>}
                        </p>
                      ) : item.detail ? (
                        <p className="text-[var(--text-secondary)]">
                          <span>{item.detail}</span>
                          {item.date && <span className="text-[var(--text-muted)]"> • {item.date}</span>}
                        </p>
                      ) : item.date ? (
                        <p className="text-[var(--text-muted)]">Tracked: {item.date}</p>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[var(--border)]/60 flex justify-end">
                    <button
                      type="button"
                      onClick={() => {
                        if (onUseTopic) {
                          onUseTopic('quiz', item.topic, item.document_id, {
                            documentName: item.document_name,
                            source: 'study-progress',
                            quizMode: 'topic',
                            difficulty: 'medium',
                            numQuestions: 10,
                          })
                        }
                      }}
                      className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--accent)] border border-[var(--accent)]/30 transition-all hover:bg-[var(--accent)] hover:text-white focus-visible"
                    >
                      <span>Quiz me on this</span>
                      <ArrowRight className="size-3" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ── Quiz Attempt History Section ───────────────────────────── */}
      {quizAttempts.length > 0 && (
        <section className="space-y-3 pt-2">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider flex items-center gap-2">
            <Trophy className="size-4 text-[var(--warning)]" />
            Quiz Attempt History
          </h3>
          <div className="rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] overflow-hidden shadow-sm">
            <div className="divide-y divide-[var(--border)]/60">
              {quizAttempts.map((attempt, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-3 text-xs">
                  <div>
                    <span className="font-semibold text-[var(--text-primary)] block text-xs">
                      {attempt.topic}
                    </span>
                    <span className="text-[11px] text-[var(--text-muted)] font-mono-numbers">
                      {attempt.date}
                    </span>
                  </div>
                  <span className="font-mono-numbers text-xs font-semibold text-[var(--warning)] bg-[var(--warning-soft)] px-2.5 py-1 rounded-full border border-[var(--warning)]/30">
                    {attempt.formatted_score || attempt.score}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
