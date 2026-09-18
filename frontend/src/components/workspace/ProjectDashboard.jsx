import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  ArrowRight,
  BookOpen,
  Brain,
  Calendar,
  FileText,
  FolderKanban,
  GraduationCap,
  Lightbulb,
  RefreshCw,
  ServerCog,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react'
import { getDocuments, getProjectAnalytics, retryIngestionJob } from '../../api/client'
import { dismissRecommendation } from '../../lib/learningApi'
import {
  ActivityItem,
  EmptyState,
  GrowthBadge,
  JobStatePill,
  LoadingBlock,
  MasteryBar,
  PageHeader,
  Panel,
  RecommendationCard,
  StatCard,
} from '../ui/primitives'
import { describeEvent, formatDelta, growthOf, masteryBand, rankMastery, relativeTime, STUDY_FLOW } from '../../lib/learning'

/* ── Overall-progress ring ─────────────────────────────────────── */
function MasteryRing({ value = 0, size = 148, stroke = 11 }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (clamped / 100) * circumference

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`Overall progress ${clamped}%`}>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--surface-3)" strokeWidth={stroke} fill="transparent" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="url(#masteryRingGradient)"
          strokeWidth={stroke}
          fill="transparent"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
        />
        <defs>
          <linearGradient id="masteryRingGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent-teal)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute text-center">
        <p className="font-mono-numbers text-3xl font-bold text-[var(--text-primary)]">{clamped}%</p>
        <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">Overall progress</p>
      </div>
    </div>
  )
}

/* ── Mastery-over-time sparkline from real evidence history ────── */
function GrowthSparkline({ points = [] }) {
  const scores = points.map((point) => point.score).filter((score) => typeof score === 'number')
  if (scores.length < 2) return null

  const width = 132
  const height = 34
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const span = max - min || 1
  const step = width / (scores.length - 1)
  const coords = scores.map((score, index) => [index * step, height - ((score - min) / span) * (height - 6) - 3])
  const path = coords.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')

  return (
    <svg width={width} height={height} className="shrink-0" aria-hidden="true">
      <path d={path} fill="none" stroke="var(--accent-teal)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      {coords.map(([x, y], index) => (
        <circle key={index} cx={x} cy={y} r={index === coords.length - 1 ? 2.75 : 1.5} fill="var(--accent-teal)" />
      ))}
    </svg>
  )
}

/** The PRD's guided path: Materials → Tutor → Quiz → Assess → Growth → Analytics. */
function StudyFlow({ onOpenWorkspace }) {
  return (
    <ol className="flex flex-wrap items-stretch gap-2">
      {STUDY_FLOW.map((step, index) => (
        <li key={step.id} className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onOpenWorkspace?.(step.id)}
            title={step.description}
            className="group flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-left transition hover:border-[var(--accent)]/45 hover:bg-[var(--surface-2)]"
          >
            <span className="grid size-6 shrink-0 place-items-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)] transition group-hover:border-[var(--accent)]/40">
              <step.icon className="size-3.5" />
            </span>
            <span className="min-w-0">
              <span className="block text-[11px] font-bold text-[var(--text-primary)]">{step.label}</span>
              <span className="hidden text-[10px] text-[var(--text-muted)] sm:block">{step.description}</span>
            </span>
          </button>
          {index < STUDY_FLOW.length - 1 && <ArrowRight className="size-3 shrink-0 text-[var(--text-muted)]/50" />}
        </li>
      ))}
    </ol>
  )
}

export default function ProjectDashboard({ threadId, onOpenWorkspace, onUseTopic }) {
  const [data, setData] = useState(null)
  const [documents, setDocuments] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [retryingJob, setRetryingJob] = useState(null)
  const [dismissed, setDismissed] = useState([])

  async function load() {
    if (!threadId) return
    setLoading(true)
    setError('')
    try {
      const [analytics, docs] = await Promise.all([
        getProjectAnalytics(threadId),
        getDocuments(threadId).catch(() => []),
      ])
      setData(analytics)
      setDocuments(docs ?? [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setDismissed([])
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId])

  const masteryRows = useMemo(() => rankMastery(data?.mastery ?? []), [data])
  const overall = data?.overall_progress ?? null
  const weakest = masteryRows[0] ?? null
  const assessmentAverage = data?.assessment_average ?? null
  const jobs = data?.ingestion ?? []
  const failedJobs = jobs.filter((job) => job.status === 'failed')

  const recommendations = useMemo(
    () => (data?.recommendations ?? []).filter((item) => !dismissed.includes(item.id)),
    [data, dismissed],
  )
  const latestActivity = data?.latest_activity ?? null

  /** Prefer the persisted recommendation; fall back to the weakest concept. */
  const nextStep = recommendations[0] ?? null
  const nextStepConcept = nextStepConceptName(nextStep, masteryRows)
  const improving = masteryRows.filter((row) => growthOf(row) === 'improving').length
  const attention = masteryRows.filter((row) => growthOf(row) === 'needs_attention').length

  async function handleDismiss(id) {
    setDismissed((prev) => [...prev, id])
    try {
      await dismissRecommendation(id)
    } catch {
      setDismissed((prev) => prev.filter((item) => item !== id))
    }
  }

  async function handleRetry(jobId) {
    setRetryingJob(jobId)
    try {
      await retryIngestionJob(jobId)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setRetryingJob(null)
    }
  }

  if (!threadId) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6">
        <EmptyState
          icon={FolderKanban}
          title="No project selected"
          description="Choose a project from the sidebar or the project switcher above to see its learning state."
        />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={Target}
        title={data?.project?.title || 'Project Analytics'}
        subtitle={data?.project?.description || 'Overall progress, concepts, growth, performance and the next best action for this project.'}
        actions={
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          >
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        }
      >
        {data?.project?.learning_goal && (
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent)]">
            <Target className="size-3" /> Goal: {data.project.learning_goal}
          </p>
        )}
      </PageHeader>

      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          {error}
        </p>
      )}

      {loading && !data ? (
        <LoadingBlock label="Loading project analytics" rows={4} />
      ) : (
        <>
          {/* ── Guided path: Materials → Tutor → Quiz → Assess → Growth → Analytics ── */}
          <Panel title="Continue this project" subtitle="Follow the loop, or jump straight to any step" icon={Sparkles}>
            <StudyFlow onOpenWorkspace={onOpenWorkspace} />
          </Panel>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Materials" value={data?.documents ?? 0} icon={FileText} tone="blue" hint="Indexed documents" />
            <StatCard
              label="Learning performance"
              value={assessmentAverage == null ? '—' : `${Math.round(assessmentAverage)}%`}
              icon={GraduationCap}
              tone="success"
              hint={
                assessmentAverage == null
                  ? 'No graded assessments yet'
                  : `${data?.assessments_graded ?? 0} graded · avg overall score`
              }
            />
            <StatCard
              label="Concepts tracked"
              value={masteryRows.length}
              icon={Brain}
              tone="teal"
              hint={masteryRows.length === 0 ? 'Take a quiz to start' : `${improving} improving · ${attention} need attention`}
            />
            <StatCard
              label="Job health"
              value={jobs.length === 0 ? '—' : `${jobs.length - failedJobs.length}/${jobs.length}`}
              icon={ServerCog}
              tone={failedJobs.length ? 'danger' : 'accent'}
              hint={failedJobs.length ? `${failedJobs.length} failed` : 'Ingestion pipeline'}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            {/* ── Progress + next step ─────────────────────────────── */}
            <div className="space-y-6">
              <Panel title="Overall progress" subtitle="Recency-weighted concept mastery estimate" icon={Activity}>
                <div className="flex flex-col items-center gap-5 sm:flex-row">
                  <MasteryRing value={overall ?? 0} />
                  <div className="w-full space-y-3">
                    {overall == null ? (
                      <p className="text-xs leading-relaxed text-[var(--text-muted)]">
                        Progress appears once you complete a quiz or an open-ended assessment. Mastery is an estimate
                        that evolves as new evidence arrives.
                      </p>
                    ) : (
                      <>
                        <div className="flex flex-wrap items-center gap-2">
                          <GrowthBadge classification={growthOf(masteryRows[0] ?? {})} />
                          <span className="text-[11px] text-[var(--text-muted)]">
                            {masteryBand(overall).label} band across {masteryRows.length} concept
                            {masteryRows.length === 1 ? '' : 's'}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {masteryRows.slice(0, 3).map((row) => (
                            <MasteryBar
                              key={row.concept_id ?? row.concept}
                              concept={row.concept}
                              score={row.score}
                              attempts={row.attempts}
                            />
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </Panel>

              <Panel title="Recommended next step" subtitle="Derived from your mastery, mistakes and activity" icon={Lightbulb}>
                {nextStep ? (
                  <div className="space-y-3">
                    <RecommendationCard
                      trigger={nextStep.trigger}
                      text={nextStep.text}
                      action={nextStepConcept ? `Practise “${nextStepConcept}”` : 'Open the Tutor'}
                      onAction={() =>
                        nextStepConcept ? onUseTopic?.('quiz', nextStepConcept) : onOpenWorkspace?.('chat')
                      }
                    />
                    <button
                      type="button"
                      onClick={() => handleDismiss(nextStep.id)}
                      className="text-[11px] font-semibold text-[var(--text-muted)] transition hover:text-[var(--text-primary)]"
                    >
                      Mark as done
                    </button>
                  </div>
                ) : weakest ? (
                  <RecommendationCard
                    trigger={weakest.score < 60 ? 'low_mastery' : 'improving'}
                    text={`Your weakest concept in this project is “${weakest.concept}” at ${Math.round(weakest.score)}% mastery across ${weakest.attempts} attempt(s). Review the related material, then take a short assessment.`}
                    action={`Practise “${weakest.concept}”`}
                    onAction={() => onUseTopic?.('quiz', weakest.concept)}
                  />
                ) : (
                  <EmptyState
                    icon={Target}
                    title="Not enough evidence yet"
                    description="Upload material and take a quiz or an open-ended assessment to build mastery evidence and unlock a recommendation."
                  />
                )}
              </Panel>

              <Panel title="Latest activity" subtitle="The most recent thing that happened here" icon={Calendar}>
                {latestActivity ? (
                  <ul className="divide-y divide-[var(--border)]">
                    <ActivityItem
                      label={describeEvent(latestActivity.type).label}
                      detail={
                        latestActivity.payload?.filename ||
                        latestActivity.payload?.title ||
                        latestActivity.payload?.topic ||
                        latestActivity.payload?.concept ||
                        null
                      }
                      timestamp={relativeTime(latestActivity.created_at)}
                      icon={describeEvent(latestActivity.type).icon}
                      tone={describeEvent(latestActivity.type).tone}
                    />
                  </ul>
                ) : (
                  <EmptyState icon={Activity} title="No activity yet" description="Tutor turns, uploads, quizzes and assessments land here." />
                )}
              </Panel>
            </div>

            {/* ── Mastery + growth ─────────────────────────────────── */}
            <div className="space-y-6">
              <Panel
                title="Concept mastery & growth"
                subtitle="Each concept is classified from its own mastery history"
                icon={Brain}
              >
                {masteryRows.length === 0 ? (
                  <EmptyState
                    icon={Brain}
                    title="No concepts tracked yet"
                    description="Concepts are recorded as you practise — take an adaptive quiz or an open-ended assessment to start building the picture."
                    action={
                      <button
                        type="button"
                        onClick={() => onOpenWorkspace?.('assessment')}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent)] px-3 py-1.5 text-xs font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)]"
                      >
                        <GraduationCap className="size-3.5" /> Start an assessment
                      </button>
                    }
                  />
                ) : (
                  <ul className="space-y-5">
                    {masteryRows.map((row) => {
                      const classification = growthOf(row)
                      const delta = formatDelta(row.delta)
                      return (
                        <li key={row.concept_id ?? row.concept} className="space-y-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="flex items-center gap-2">
                              <GrowthBadge classification={classification} />
                              {row.samples > 1 && delta && delta !== 'no change' && (
                                <span className="font-mono-numbers text-[11px] font-semibold text-[var(--text-muted)]">
                                  {delta} since last evidence
                                </span>
                              )}
                            </span>
                            <GrowthSparkline points={row.history ?? []} />
                          </div>
                          <MasteryBar
                            concept={row.concept}
                            score={row.score}
                            attempts={row.attempts}
                            tone={row.score >= 75 ? 'success' : row.score >= 60 ? 'accent' : 'danger'}
                          />
                        </li>
                      )
                    })}
                  </ul>
                )}
              </Panel>

              {/* ── Background processing ──────────────────────────── */}
              <Panel
                title="Background processing"
                subtitle="Material ingestion jobs for this project"
                icon={ServerCog}
                action={
                  failedJobs.length > 0 && (
                    <span className="rounded-full border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-2 py-0.5 text-[10px] font-bold uppercase text-[var(--danger)]">
                      {failedJobs.length} failed
                    </span>
                  )
                }
              >
                {jobs.length === 0 ? (
                  <EmptyState
                    icon={FileText}
                    title="No ingestion jobs yet"
                    description="Upload a PDF in Materials — processing runs in the background and appears here."
                  />
                ) : (
                  <ul className="divide-y divide-[var(--border)]">
                    {jobs.map((job) => {
                      const doc = documents.find((item) => item.id === job.document_id)
                      return (
                        <li key={job.id} className="flex items-center justify-between gap-3 py-2.5">
                          <div className="min-w-0">
                            <p className="truncate text-xs font-medium text-[var(--text-primary)]">
                              {doc?.filename ?? `Document ${String(job.document_id).slice(0, 8)}`}
                            </p>
                            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">
                              {job.retry_count ? `Retried ${job.retry_count}× · ` : ''}
                              {job.error_msg || 'Indexed for retrieval'}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <JobStatePill state={job.status} />
                            {job.status === 'failed' && (
                              <button
                                type="button"
                                onClick={() => handleRetry(job.id)}
                                disabled={retryingJob === job.id}
                                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2 py-1 text-[10px] font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)] disabled:opacity-50"
                              >
                                <RefreshCw className={`size-3 ${retryingJob === job.id ? 'animate-spin' : ''}`} /> Retry
                              </button>
                            )}
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </Panel>

              {/* ── Activity ──────────────────────────────────────── */}
              <Panel title="Recent activity" subtitle="Learning events for this project" icon={Calendar}>
                {(data?.activity ?? []).length === 0 ? (
                  <EmptyState icon={Activity} title="No activity recorded yet" description="Tutor turns, uploads, quizzes and assessments land here." />
                ) : (
                  <ul className="divide-y divide-[var(--border)]">
                    {data.activity
                      .filter((item) => item.type !== 'mastery_updated')
                      .slice(0, 10)
                      .map((item) => {
                        const meta = describeEvent(item.type)
                        return (
                          <ActivityItem
                            key={item.id}
                            label={meta.label}
                            detail={
                              item.payload?.filename ||
                              item.payload?.title ||
                              item.payload?.topic ||
                              item.payload?.concept ||
                              null
                            }
                            timestamp={relativeTime(item.created_at)}
                            icon={meta.icon}
                            tone={meta.tone}
                          />
                        )
                      })}
                  </ul>
                )}
              </Panel>
            </div>
          </div>

          <p className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
            <TrendingUp className="size-3" />
            Mastery is an estimate, not a claim of perfect measurement — it moves as new quizzes, assessments and
            activity provide evidence.
            <BookOpen className="ml-1 size-3" />
          </p>
        </>
      )}
    </div>
  )
}

/** Resolve the concept a recommendation refers to, for the deep-link action. */
function nextStepConceptName(recommendation, masteryRows) {
  if (!recommendation) return null
  const matched = masteryRows.find((row) => row.concept_id && row.concept_id === recommendation.concept_id)
  if (matched) return matched.concept
  const byName = masteryRows.find((row) => recommendation.text?.includes(row.concept))
  return byName?.concept ?? masteryRows[0]?.concept ?? null
}
