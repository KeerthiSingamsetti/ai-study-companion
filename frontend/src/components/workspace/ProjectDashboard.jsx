import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  BookOpen,
  Brain,
  Calendar,
  FileText,
  FolderKanban,
  GraduationCap,
  Layers,
  Lightbulb,
  ListChecks,
  MessageSquare,
  RefreshCw,
  ServerCog,
  Target,
} from 'lucide-react'
import { getDocuments, getProjectAnalytics, retryIngestionJob } from '../../api/client'
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
import { classifyScore, describeEvent, masteryBand, rankMastery, relativeTime } from '../../lib/learning'

function MasteryRing({ value = 0, size = 132, stroke = 10 }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (clamped / 100) * circumference

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
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
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
        <defs>
          <linearGradient id="masteryRingGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent-teal)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute text-center">
        <p className="font-mono-numbers text-2xl font-bold text-[var(--text-primary)]">{clamped}%</p>
        <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Mastery</p>
      </div>
    </div>
  )
}

export default function ProjectDashboard({ threadId, onOpenWorkspace, onUseTopic }) {
  const [data, setData] = useState(null)
  const [documents, setDocuments] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [retryingJob, setRetryingJob] = useState(null)

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
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId])

  const masteryRows = useMemo(() => rankMastery(data?.mastery ?? []), [data])
  const overall = useMemo(() => {
    const scores = masteryRows.map((row) => row.score).filter((score) => typeof score === 'number')
    if (scores.length === 0) return null
    return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
  }, [masteryRows])

  const weakest = masteryRows[0] ?? null
  const assessmentAverage = data?.assessment_average ?? null
  const jobs = data?.ingestion ?? []
  const failedJobs = jobs.filter((job) => job.status === 'failed')

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
          description="Choose a project from the sidebar or the project switcher above to see its learning analytics."
        />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={Target}
        title={data?.project?.title || 'Project Analytics'}
        subtitle="Progress, concepts, mastery growth and the next best action for this project."
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
        <div className="mt-3 flex flex-wrap gap-2">
          {[
            { label: 'Open Tutor', icon: MessageSquare, target: 'chat' },
            { label: 'Materials', icon: BookOpen, target: 'documents' },
            { label: 'Practice quiz', icon: ListChecks, target: 'quiz' },
            { label: 'Flashcards', icon: Layers, target: 'flashcards' },
          ].map((action) => (
            <button
              key={action.target}
              type="button"
              onClick={() => onOpenWorkspace?.(action.target)}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-3 py-1.5 text-[11px] font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)]"
            >
              <action.icon className="size-3" /> {action.label}
            </button>
          ))}
        </div>
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Materials" value={data?.documents ?? 0} icon={FileText} tone="blue" hint="Indexed documents" />
            <StatCard
              label="Assessments"
              value={assessmentAverage == null ? '—' : `${Math.round(assessmentAverage)}%`}
              icon={GraduationCap}
              tone="success"
              hint={assessmentAverage == null ? 'No graded answers yet' : 'Average overall score'}
            />
            <StatCard label="Concepts tracked" value={masteryRows.length} icon={Brain} tone="teal" hint="With mastery evidence" />
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
              <Panel title="Overall progress" subtitle="Recency-weighted concept mastery" icon={Activity}>
                <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
                  <MasteryRing value={overall ?? 0} />
                  <div className="w-full space-y-3">
                    {overall == null ? (
                      <p className="text-xs leading-relaxed text-[var(--text-muted)]">
                        Mastery appears once you complete a quiz or an open-ended assessment for this project.
                      </p>
                    ) : (
                      <>
                        <div className="flex items-center gap-2">
                          <GrowthBadge classification={classifyScore(overall)} />
                          <span className="text-[11px] text-[var(--text-muted)]">
                            {masteryBand(overall).label} band across {masteryRows.length} concept{masteryRows.length === 1 ? '' : 's'}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {masteryRows.slice(0, 3).map((row) => (
                            <MasteryBar key={row.concept} concept={row.concept} score={row.score} attempts={row.attempts} />
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </Panel>

              <Panel title="Recommended next step" subtitle="Derived from your weakest evidence" icon={Lightbulb}>
                {weakest ? (
                  <RecommendationCard
                    trigger={weakest.score < 60 ? 'low_mastery' : 'improving'}
                    text={`Your weakest concept in this project is “${weakest.concept}” at ${Math.round(weakest.score)}% mastery across ${weakest.attempts} attempt(s). Practise it with a focused quiz, then re-check your mastery.`}
                    action={`Practise “${weakest.concept}”`}
                    onAction={() => onUseTopic?.('quiz', weakest.concept)}
                  />
                ) : (
                  <EmptyState
                    icon={Target}
                    title="Not enough evidence yet"
                    description="Complete a quiz or upload material and ask the Tutor a question to build mastery evidence."
                  />
                )}
              </Panel>
            </div>

            {/* ── Mastery + growth ─────────────────────────────────── */}
            <div className="space-y-6">
              <Panel
                title="Concept mastery & growth"
                subtitle="Each concept is classified as improving, stable or needing attention"
                icon={Brain}
              >
                {masteryRows.length === 0 ? (
                  <EmptyState
                    icon={Brain}
                    title="No concepts tracked yet"
                    description="Concepts are recorded as you practise — take an adaptive quiz to start building the picture."
                  />
                ) : (
                  <ul className="space-y-4">
                    {masteryRows.map((row) => (
                      <li key={row.concept} className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <GrowthBadge classification={classifyScore(row.score)} />
                          <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                            {masteryBand(row.score).label}
                          </span>
                        </div>
                        <MasteryBar concept={row.concept} score={row.score} attempts={row.attempts} tone={
                          row.score >= 75 ? 'success' : row.score >= 60 ? 'accent' : 'danger'
                        } />
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              {/* ── Background processing ──────────────────────────── */}
              <Panel
                title="Background processing"
                subtitle="Material ingestion jobs for this project"
                icon={ServerCog}
                action={failedJobs.length > 0 && (
                  <span className="rounded-full border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-2 py-0.5 text-[10px] font-bold uppercase text-[var(--danger)]">
                    {failedJobs.length} failed
                  </span>
                )}
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
                    {data.activity.slice(0, 10).map((item) => {
                      const meta = describeEvent(item.type)
                      return (
                        <ActivityItem
                          key={item.id}
                          label={meta.label}
                          detail={item.payload?.filename || item.payload?.title || item.payload?.topic || null}
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
        </>
      )}
    </div>
  )
}
