import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertCircle,
  ArrowRight,
  Brain,
  CheckCircle2,
  FileText,
  Gauge,
  GraduationCap,
  Lightbulb,
  Loader2,
  MessageSquare,
  RefreshCw,
  Send,
  SquarePen,
  Target,
  TrendingUp,
} from 'lucide-react'
import { getProjectAnalytics } from '../../api/client'
import { generateAssessment, getAssessmentSummary, gradeAssessment } from '../../lib/learningApi'
import {
  EmptyState,
  GrowthBadge,
  LoadingBlock,
  MasteryBar,
  PageHeader,
  Panel,
  StatCard,
} from '../ui/primitives'
import { CONFIDENCE_OPTIONS, calibrationMeta, formatDelta, growthOf, relativeTime } from '../../lib/learning'

const fieldClass =
  'w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]/70 focus:bg-[var(--surface-3)]'

const DIFFICULTIES = [
  { id: 'easy', label: 'Easy' },
  { id: 'medium', label: 'Medium' },
  { id: 'hard', label: 'Hard' },
]

function ScoreDial({ label, value, tone }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value ?? 0)))
  const gradient = {
    success: 'from-emerald-400 to-teal-400',
    accent: 'from-[var(--accent)] to-amber-300',
    danger: 'from-rose-400 to-orange-400',
  }[tone ?? (clamped >= 75 ? 'success' : clamped >= 60 ? 'accent' : 'danger')]

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{label}</span>
        <span className="font-mono-numbers text-sm font-bold text-[var(--text-primary)]">{clamped}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-3)]">
        <motion.div
          className={`h-full rounded-full bg-gradient-to-r ${gradient}`}
          initial={{ width: 0 }}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

/**
 * Expected vs produced. Two bars on the same 0-100 axis is the whole idea: when
 * the grey bar sits well above the amber one, the learner is studying something
 * that feels known. Rendered only when both numbers exist.
 */
function CalibrationBars({ predicted, actual }) {
  if (typeof predicted !== 'number' || typeof actual !== 'number') return null
  const rows = [
    { label: 'Expected', value: predicted, color: 'var(--text-muted)' },
    { label: 'Actually scored', value: actual, color: 'var(--accent)' },
  ]
  return (
    <div className="space-y-2.5">
      {rows.map((row) => (
        <div key={row.label} className="space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              {row.label}
            </span>
            <span className="font-mono-numbers text-[11px] font-bold text-[var(--text-primary)]">
              {Math.round(row.value)}%
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-3)]">
            <motion.div
              className="h-full rounded-full"
              style={{ background: row.color }}
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(0, Math.min(100, row.value))}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Immediate calibration feedback on the answer that was just graded. */
function CalibrationCard({ snapshot }) {
  if (!snapshot) return null
  const meta = calibrationMeta(snapshot.direction)
  // One decimal, exactly as the API reports it — rounding here would disagree
  // with the headline sentence for gaps sitting on a .5 boundary.
  const bias = Math.round((snapshot.bias ?? 0) * 10) / 10
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
          <Gauge className="size-3.5 text-[var(--accent)]" /> Confidence calibration
        </span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${meta.cls}`}>
          {meta.label}
        </span>
      </div>
      <div className="mt-3 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <CalibrationBars predicted={snapshot.mean_predicted} actual={snapshot.mean_actual} />
        <div className="text-center">
          <p className="font-mono-numbers text-2xl font-bold text-[var(--text-primary)]">
            {bias > 0 ? '+' : ''}
            {bias}
          </p>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">point gap</p>
        </div>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-[var(--text-secondary)]">{snapshot.insight}</p>
    </div>
  )
}

export default function AssessmentWorkspace({ threadId, documents = [], prefill, onOpenWorkspace }) {
  const [mastery, setMastery] = useState([])
  const [overall, setOverall] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)

  const [concept, setConcept] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [documentId, setDocumentId] = useState('')

  const [question, setQuestion] = useState(null)
  const [answer, setAnswer] = useState('')
  const [generating, setGenerating] = useState(false)
  const [grading, setGrading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  // Self-reported confidence, captured before the answer is graded. This is the
  // only signal in the product that measures what the learner *believes* they
  // know, and the gap between belief and result is what calibration reports.
  const [confidence, setConfidence] = useState(null)

  const predictedScore = CONFIDENCE_OPTIONS.find((option) => option.level === confidence)?.score ?? null

  const readyDocuments = useMemo(
    () => documents.filter((doc) => doc.chunk_count > 0 || doc.page_count > 0),
    [documents],
  )

  async function load() {
    if (!threadId) return
    setLoading(true)
    try {
      const [analytics, summaryData] = await Promise.all([
        getProjectAnalytics(threadId),
        getAssessmentSummary(threadId).catch(() => null),
      ])
      const rows = analytics?.mastery ?? []
      setMastery(rows)
      setOverall(analytics?.overall_progress ?? null)
      setSummary(summaryData)
      // Default to the weakest concept — that is where evidence helps most.
      setConcept((current) => current || rows[0]?.concept || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setQuestion(null)
    setResult(null)
    setAnswer('')
    setConfidence(null)
    setError('')
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId])

  useEffect(() => {
    if (prefill?.topic) setConcept(prefill.topic)
    if (prefill?.documentId) setDocumentId(prefill.documentId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill])

  const weakest = mastery[0] ?? null

  async function startAssessment(event) {
    event?.preventDefault?.()
    if (!concept.trim()) {
      setError('Choose or type a concept to be assessed on.')
      return
    }
    setGenerating(true)
    setError('')
    setResult(null)
    setAnswer('')
    setConfidence(null)
    try {
      const generated = await generateAssessment({
        projectId: threadId,
        concept: concept.trim(),
        documentId: documentId || undefined,
        numQuestions: 1,
        difficulty,
      })
      setQuestion(generated.questions?.[0] ?? null)
      if (!generated.questions?.length) setError('The assessment model returned no questions. Try again.')
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  async function submitAnswer(event) {
    event?.preventDefault?.()
    if (!answer.trim() || !question) return
    setGrading(true)
    setError('')
    try {
      const graded = await gradeAssessment({
        projectId: threadId,
        concept: concept.trim(),
        question: question.question,
        answer: answer.trim(),
        referenceAnswer: question.reference_answer,
        rubric: question.rubric,
        documentId: documentId || undefined,
        difficulty,
        predictedScore,
      })
      setResult(graded)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setGrading(false)
    }
  }

  if (!threadId) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6">
        <EmptyState
          icon={SquarePen}
          title="No project selected"
          description="Open a project to run an open-ended assessment against its material."
        />
      </div>
    )
  }

  const history = summary?.history ?? []

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={SquarePen}
        title="Open-ended Assessment"
        subtitle="Explain a concept in your own words. Your answer is graded against your own course material — no outside knowledge — and moves your mastery estimate."
        actions={
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          >
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        }
      />

      {error && (
        <p role="alert" className="flex items-start gap-2 rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" /> {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Graded answers" value={summary?.graded_count ?? 0} icon={GraduationCap} tone="success" hint="Open-ended attempts" />
        <StatCard
          label="Assessment average"
          value={summary?.assessment_average == null ? '—' : `${Math.round(summary.assessment_average)}%`}
          icon={TrendingUp}
          tone="accent"
          hint="Mean overall score"
        />
        <StatCard
          label="Overall progress"
          value={overall == null ? '—' : `${Math.round(overall)}%`}
          icon={Brain}
          tone="teal"
          hint={mastery.length === 0 ? 'No concepts tracked yet' : `${mastery.length} concept${mastery.length === 1 ? '' : 's'} tracked`}
        />
      </div>

      {readyDocuments.length === 0 && (
        <Panel title="Material required" subtitle="Assessment questions are grounded in your uploads" icon={FileText}>
          <EmptyState
            icon={FileText}
            title="No processed material in this project"
            description="Upload a PDF in Materials first — questions and grading both come from your own course content."
            action={
              <button
                type="button"
                onClick={() => onOpenWorkspace?.('documents')}
                className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent)] px-3 py-1.5 text-xs font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)]"
              >
                Open Materials <ArrowRight className="size-3.5" />
              </button>
            }
          />
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        {/* ── Assessment flow ──────────────────────────────────────── */}
        <div className="space-y-6">
          <Panel
            title={question ? 'Your answer' : 'Choose what to be assessed on'}
            subtitle={question ? 'Write an explanation, then submit it for grounded grading' : 'Pick a tracked concept or type your own'}
            icon={SquarePen}
          >
            {!question ? (
              <form onSubmit={startAssessment} className="space-y-4">
                <label className="block space-y-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Concept</span>
                  <input
                    className={fieldClass}
                    value={concept}
                    onChange={(event) => setConcept(event.target.value)}
                    placeholder={weakest ? `e.g. ${weakest.concept}` : 'e.g. Gradient descent'}
                    list="assessment-concepts"
                  />
                  <datalist id="assessment-concepts">
                    {mastery.map((row) => (
                      <option key={row.concept_id ?? row.concept} value={row.concept} />
                    ))}
                  </datalist>
                </label>

                {mastery.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {mastery.slice(0, 6).map((row) => (
                      <button
                        key={row.concept_id ?? row.concept}
                        type="button"
                        onClick={() => setConcept(row.concept)}
                        className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition ${
                          concept === row.concept
                            ? 'border-[var(--accent)]/50 bg-[var(--accent-soft)] text-[var(--accent)]'
                            : 'border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]'
                        }`}
                      >
                        {row.concept} · {Math.round(row.score)}%
                      </button>
                    ))}
                  </div>
                )}

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block space-y-1.5">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Difficulty</span>
                    <select className={fieldClass} value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                      {DIFFICULTIES.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Material</span>
                    <select className={fieldClass} value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
                      <option value="">Use the project&rsquo;s first material</option>
                      {readyDocuments.map((doc) => (
                        <option key={doc.id} value={doc.id}>
                          {doc.filename}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={generating}
                  className="inline-flex items-center gap-2 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-2.5 text-sm font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)] disabled:opacity-50"
                >
                  {generating ? <Loader2 className="size-4 animate-spin" /> : <Lightbulb className="size-4" />}
                  {generating ? 'Writing a question…' : 'Generate question'}
                </button>
              </form>
            ) : (
              <form onSubmit={submitAnswer} className="space-y-4">
                <div className="rounded-2xl border border-[var(--accent)]/25 bg-gradient-to-br from-[var(--accent-soft)] via-transparent to-transparent p-4">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                    {concept} · {difficulty}
                  </span>
                  <p className="mt-2 text-sm font-medium leading-relaxed text-[var(--text-primary)]">{question.question}</p>
                  {question.source_citation && (
                    <p className="mt-2 text-[11px] text-[var(--text-muted)]">Grounded in {question.source_citation}</p>
                  )}
                </div>

                <label className="block space-y-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Your explanation</span>
                  <textarea
                    className={`${fieldClass} min-h-[180px] resize-y leading-relaxed`}
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    placeholder="Explain it as if you were teaching it to a classmate…"
                  />
                </label>

                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                      <Gauge className="size-3.5 text-[var(--accent)]" /> Before you see the score — how well did you do?
                    </span>
                    {confidence == null && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--accent)]">
                        Pick one to unlock grading
                      </span>
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
                    {CONFIDENCE_OPTIONS.map((option) => {
                      const selected = confidence === option.level
                      return (
                        <button
                          key={option.level}
                          type="button"
                          aria-pressed={selected}
                          onClick={() => setConfidence(option.level)}
                          className={`rounded-[var(--radius-control)] border px-2 py-2 text-center transition ${
                            selected
                              ? 'border-[var(--accent)]/60 bg-[var(--accent-soft)] text-[var(--accent)]'
                              : 'border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]'
                          }`}
                        >
                          <span className="block text-[11px] font-bold">{option.label}</span>
                          <span className="mt-0.5 block font-mono-numbers text-[10px] text-[var(--text-muted)]">
                            ~{option.score}/100
                          </span>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-2.5 text-[11px] leading-relaxed text-[var(--text-muted)]">
                    Your prediction is stored with the graded result and compared with it — the gap is your calibration,
                    and knowing it is what separates studying what feels familiar from studying what you can actually retrieve.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="submit"
                    disabled={grading || !answer.trim() || confidence == null}
                    className="inline-flex items-center gap-2 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-2.5 text-sm font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)] disabled:opacity-50"
                  >
                    {grading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                    {grading ? 'Grading…' : 'Submit for grading'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setQuestion(null)
                      setAnswer('')
                      setResult(null)
                      setConfidence(null)
                    }}
                    className="rounded-[var(--radius-control)] border border-[var(--border)] px-3.5 py-2.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
                  >
                    Another concept
                  </button>
                </div>
              </form>
            )}
          </Panel>

          {/* ── Graded feedback ──────────────────────────────────── */}
          {result && (
            <Panel title="Graded feedback" subtitle="Grounded in your material, not outside knowledge" icon={GraduationCap}>
              <div className="space-y-5">
                <div className="grid gap-4 sm:grid-cols-3">
                  <ScoreDial label="Overall" value={result.overall_score} />
                  <ScoreDial label="Understanding" value={result.understanding} tone="accent" />
                  <ScoreDial label="Accuracy" value={result.accuracy} tone="accent" />
                </div>

                <p className="rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-4 text-sm leading-relaxed text-[var(--text-secondary)]">
                  {result.feedback}
                </p>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--success)]">Covered</p>
                    {result.concepts_covered?.length ? (
                      <ul className="mt-2 space-y-1.5">
                        {result.concepts_covered.map((item) => (
                          <li key={item} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                            <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-[var(--success)]" /> {item}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-[var(--text-muted)]">Nothing identified as covered.</p>
                    )}
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--danger)]">Missing</p>
                    {result.concepts_missing?.length ? (
                      <ul className="mt-2 space-y-1.5">
                        {result.concepts_missing.map((item) => (
                          <li key={item} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                            <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-[var(--danger)]" /> {item}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-[var(--text-muted)]">No gaps identified.</p>
                    )}
                  </div>
                </div>

                {result.mastery && (
                  <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="flex items-center gap-2">
                        <GrowthBadge classification={growthOf({ classification: result.mastery.growth?.classification, score: result.mastery.score })} />
                        <span className="text-xs text-[var(--text-muted)]">
                          {result.mastery.attempts} evidence point{result.mastery.attempts === 1 ? '' : 's'} on {result.mastery.concept}
                        </span>
                      </span>
                      <span className="font-mono-numbers text-xs font-semibold text-[var(--text-primary)]">
                        {formatDelta(result.mastery.growth?.delta) || 'no change'}
                      </span>
                    </div>
                    <div className="mt-3">
                      <MasteryBar concept="Updated mastery estimate" score={result.mastery.score} attempts={result.mastery.attempts} />
                    </div>
                  </div>
                )}

                <CalibrationCard snapshot={result.calibration} />

                {result.recommendations?.length > 0 && (
                  <div className="rounded-2xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] p-4">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                      Recommended next
                    </span>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--text-primary)]">{result.recommendations[0].text}</p>
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={startAssessment}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)]"
                  >
                    <RefreshCw className="size-3.5" /> Another question
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpenWorkspace?.('chat')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)]"
                  >
                    <MessageSquare className="size-3.5" /> Review with the Tutor
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpenWorkspace?.('project-dashboard')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)]"
                  >
                    <TrendingUp className="size-3.5" /> See growth
                  </button>
                </div>
              </div>
            </Panel>
          )}
        </div>

        {/* ── Growth + history ─────────────────────────────────────── */}
        <div className="space-y-6">
          <Panel title="Concept mastery & growth" subtitle="Every graded answer moves this estimate" icon={Brain}>
            {loading && mastery.length === 0 ? (
              <LoadingBlock label="Loading concepts" rows={3} />
            ) : mastery.length === 0 ? (
              <EmptyState
                icon={Target}
                title="No concepts tracked yet"
                description="Your first graded answer creates the first concept and its mastery estimate."
              />
            ) : (
              <ul className="space-y-4">
                {mastery.map((row) => (
                  <li key={row.concept_id ?? row.concept} className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <GrowthBadge classification={growthOf(row)} />
                      <span className="font-mono-numbers text-[11px] text-[var(--text-muted)]">
                        {formatDelta(row.delta) || `${row.attempts} attempt${row.attempts === 1 ? '' : 's'}`}
                      </span>
                    </div>
                    <MasteryBar
                      concept={row.concept}
                      score={row.score}
                      attempts={row.attempts}
                      tone={row.score >= 75 ? 'success' : row.score >= 60 ? 'accent' : 'danger'}
                    />
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {summary?.calibration && (
            <Panel
              title="Confidence calibration"
              subtitle="What you expected vs what you produced"
              icon={Gauge}
            >
              <div className="space-y-4">
                <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                  {summary.calibration.headline}
                </p>

                {summary.calibration.concepts.length > 0 && (
                  <ul className="space-y-3">
                    {summary.calibration.concepts.map((row) => {
                      const meta = calibrationMeta(row.direction)
                      return (
                        <li
                          key={row.concept_id}
                          className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-3"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-xs font-semibold text-[var(--text-primary)]">
                              {row.concept}
                            </span>
                            <span
                              className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${meta.cls}`}
                            >
                              {meta.label}
                            </span>
                          </div>
                          <div className="mt-2.5">
                            <CalibrationBars predicted={row.mean_predicted} actual={row.mean_actual} />
                          </div>
                          <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-muted)]">{row.insight}</p>
                        </li>
                      )
                    })}
                  </ul>
                )}

                <p className="text-[10px] leading-relaxed text-[var(--text-muted)]">
                  Predictions are compared with graded results by deterministic arithmetic — the model grades the
                  answer, never your self-awareness.
                </p>
              </div>
            </Panel>
          )}

          <Panel title="Assessment history" subtitle="Your graded explanations, newest first" icon={GraduationCap}>
            {history.length === 0 ? (
              <EmptyState
                icon={SquarePen}
                title="No graded answers yet"
                description="Submit an explanation and it will appear here with its feedback."
              />
            ) : (
              <ul className="divide-y divide-[var(--border)]">
                {history.slice(0, 6).map((item) => (
                  <li key={item.id} className="space-y-1.5 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="min-w-0 text-xs font-medium leading-snug text-[var(--text-primary)]">{item.question}</p>
                      <span className="shrink-0 font-mono-numbers text-xs font-bold text-[var(--accent)]">
                        {Math.round(item.overall_score)}%
                      </span>
                    </div>
                    <p className="flex flex-wrap items-center gap-x-3 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                      {item.concept && <span>{item.concept}</span>}
                      {typeof item.predicted_score === 'number' && (
                        <span className="font-mono-numbers">
                          expected {Math.round(item.predicted_score)}%
                        </span>
                      )}
                      <span>{relativeTime(item.created_at)}</span>
                    </p>
                    {item.feedback && (
                      <p className="line-clamp-2 text-[11px] leading-relaxed text-[var(--text-muted)]">{item.feedback}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  )
}
