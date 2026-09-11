import { useEffect, useState } from 'react'
import { generateStudyPlan } from '../../lib/plannerApi'
import IndexTab from '../common/IndexTab'

function CalendarIcon() {
  return (
    <svg className="size-5 text-[var(--accent)] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" />
    </svg>
  )
}

export default function PlannerWorkspace({
  documents = [],
  planData,
  onPlanUpdate,
  isExpanded,
  onToggleExpand,
  onUseTopic,
}) {
  const [documentId, setDocumentId] = useState(documents[0]?.id ?? '')
  const [topicsText, setTopicsText] = useState('')
  const [days, setDays] = useState(7)
  const [examDate, setExamDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState({})
  const [open, setOpen] = useState({})
  const [localPlanData, setLocalPlanData] = useState(planData)

  useEffect(() => {
    if (planData) setLocalPlanData(planData)
  }, [planData])

  const activePlan = localPlanData || planData

  // Keep documentId valid when documents prop updates
  useEffect(() => {
    if (documents.length > 0 && (!documentId || (documentId !== 'all' && !documents.some((d) => d.id === documentId)))) {
      setDocumentId(documents.length > 1 ? 'all' : documents[0].id)
    }
  }, [documents, documentId])

  const effectiveDocId = documentId || (documents.length > 1 ? 'all' : (documents[0]?.id ?? ''))

  async function generate() {
    const targetDocId = effectiveDocId === 'all' ? documents[0]?.id : effectiveDocId
    if (!targetDocId) return
    setLoading(true)
    try {
      const plan = await generateStudyPlan(
        targetDocId,
        topicsText.split(',').map((x) => x.trim()).filter(Boolean),
        days,
        examDate
      )
      setChecked({})
      setOpen({})
      setLocalPlanData(plan)
      if (onPlanUpdate) onPlanUpdate(plan)
    } finally {
      setLoading(false)
    }
  }

  // Setup Stage View
  if (!activePlan) {
    return (
      <div className="space-y-5 max-w-xl mx-auto p-4 animate-fade-in text-[var(--text-primary)] font-sans">
        {/* Header Card */}
        <div className="flex items-center gap-3 rounded.3xl border border-[var(--border)] bg-[var(--surface-1)] p-4 shadow-lg">
          <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-[var(--accent-soft)] border border-[var(--accent)]/30 text-[var(--accent)]">
            <CalendarIcon />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">Build Study Plan</h2>
            <p className="text-sm text-[var(--text-muted)]">Generate a structured day-by-day revision schedule grounded in your PDFs</p>
          </div>
        </div>

        {/* Setup Form Card */}
        <div className="space-y-4 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-5 shadow-xl">
          {/* Source Document Selection */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Source Document ({documents.length} Uploaded)
            </label>
            <select
              value={effectiveDocId}
              onChange={(e) => setDocumentId(e.target.value)}
              className="w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--accent)]"
            >
              {documents.length > 1 && (
                <option value="all">📚 All Thread PDFs ({documents.length} Files Combined)</option>
              )}
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  📄 {d.filename}
                </option>
              ))}
            </select>
          </div>

          {/* Topics Input */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Topics / Focus Areas (Optional, comma-separated)
            </label>
            <input
              value={topicsText}
              onChange={(e) => setTopicsText(e.target.value)}
              placeholder="e.g. Chapter 1, Regression, Neural Networks"
              className="w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none transition focus:border-[var(--accent)]"
            />
          </div>

          {/* Days & Exam Date Row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Duration (Days)
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={days}
                onChange={(e) => setDays(+e.target.value)}
                className="w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm font-mono-numbers text-[var(--text-primary)] outline-none transition focus:border-[var(--accent)]"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Exam Target Date
              </label>
              <input
                type="date"
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                className="w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--accent)]"
              />
            </div>
          </div>

          {/* Submit Button */}
          <button
            disabled={loading || !effectiveDocId}
            onClick={generate}
            className="w-full rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white shadow-md transition hover:bg-[var(--accent-strong)] disabled:opacity-50 focus-visible mt-2 cursor-pointer"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Generating Schedule…
              </span>
            ) : (
              'Generate Study Plan'
            )}
          </button>
        </div>
      </div>
    )
  }

  // Result Stage View
  const daysList = Array.isArray(activePlan?.days) ? activePlan.days : []
  const tasks = daysList.flatMap((day) =>
    (day.tasks || []).map((_, index) => `${day.day}-${index}`)
  )
  const done = tasks.filter((key) => checked[key]).length

  return (
    <div className="space-y-5 p-4 max-w-2xl mx-auto text-[var(--text-primary)] font-sans animate-fade-in">
      {/* ── Plan Header & Progress Bar ────────────────────────────── */}
      <div className="rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-4 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IndexTab variant="accent">{activePlan.num_days ?? daysList.length}-Day Plan</IndexTab>
            <span className="text-sm text-[var(--text-muted)] font-mono-numbers font-medium">
              {done} / {tasks.length} tasks completed
            </span>
          </div>

          <div className="flex items-center gap-3 text-sm font-semibold">
            {onToggleExpand && (
              <button onClick={onToggleExpand} className="text-[var(--text-secondary)] hover:text-white transition">
                {isExpanded ? 'Collapse' : 'Expand'}
              </button>
            )}
            <button onClick={generate} className="text-[var(--accent)] hover:underline">
              Regenerate
            </button>
            <button
              onClick={() => {
                setLocalPlanData(null)
                if (onPlanUpdate) onPlanUpdate(null)
              }}
              className="text-[var(--text-secondary)] hover:text-white transition"
            >
              + New Plan
            </button>
          </div>
        </div>

        {/* Progress Track */}
        <div className="h-2 w-full rounded-full bg-[var(--surface-2)] overflow-hidden">
          <div
            className="h-full bg-[var(--success)] transition-all duration-300 ease-out"
            style={{ width: `${tasks.length ? (done / tasks.length) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* ── Day Cards List ───────────────────────────────────────── */}
      <div className="space-y-4">
        {daysList.map((day) => (
          <section
            key={day.day}
            className="rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-4 shadow-md space-y-3 transition hover:border-[var(--border-strong)]"
          >
            <button
              onClick={() => setOpen((p) => ({ ...p, [day.day]: !p[day.day] }))}
              className="flex w-full items-center justify-between text-left focus-visible rounded-lg p-1"
            >
              <div className="flex items-center gap-3">
                <IndexTab variant="accent">Day {day.day}</IndexTab>
                <span className="text-sm font-semibold text-[var(--text-primary)]">
                  {day.focus}
                </span>
              </div>
              <span className="text-xs text-[var(--text-muted)] font-mono-numbers">
                {open[day.day] ? '▲' : '▼'}
              </span>
            </button>

            {open[day.day] && (
              <div className="space-y-3 pt-3 border-t border-[var(--border)]/60 animate-accordion-down">
                {/* Day Topic Chips */}
                <div className="flex flex-wrap gap-1.5">
                  {(day.topics || []).map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-[var(--surface-2)] border border-[var(--border)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]"
                    >
                      {t}
                    </span>
                  ))}
                </div>

                {/* Day Tasks Checklist */}
                <div className="space-y-2">
                  {(day.tasks || []).map((task, i) => {
                    const key = `${day.day}-${i}`
                    const isChecked = !!checked[key]
                    return (
                      <label
                        key={key}
                        className="flex items-start gap-2.5 text-sm text-[var(--text-primary)] cursor-pointer select-none rounded-lg p-1.5 hover:bg-[var(--surface-2)] transition"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => setChecked((p) => ({ ...p, [key]: !p[key] }))}
                          className="mt-1 rounded border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--accent)] focus:ring-0 cursor-pointer"
                        />
                        <span className={isChecked ? 'line-through text-[var(--text-muted)] font-normal' : 'leading-relaxed font-normal'}>
                          {task}
                        </span>
                      </label>
                    )
                  })}
                </div>

                {/* Quick Topic Action Buttons */}
                {onUseTopic && day.topics && day.topics[0] && (
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => onUseTopic('quiz', day.topics[0])}
                      className="text-sm font-semibold text-[var(--accent)] hover:underline flex items-center gap-1"
                    >
                      <span>Practice Quiz →</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onUseTopic('flashcards', day.topics[0])}
                      className="text-sm font-semibold text-[var(--success)] hover:underline flex items-center gap-1"
                    >
                      <span>Study Flashcards →</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  )
}
