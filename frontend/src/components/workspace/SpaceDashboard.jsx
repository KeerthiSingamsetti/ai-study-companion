import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  ArrowUpRight,
  Boxes,
  Compass,
  FileText,
  FolderKanban,
  Layers,
  RefreshCw,
  Sparkles,
  Target,
} from 'lucide-react'
import { getSpaceAnalytics } from '../../api/client'
import {
  ActivityItem,
  EmptyState,
  GrowthBadge,
  LoadingBlock,
  MasteryBar,
  PageHeader,
  Panel,
  StatCard,
} from '../ui/primitives'
import { describeEvent, relativeTime } from '../../lib/learning'

function ProgressRing({ value = 0, size = 122, stroke = 10 }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`Space progress ${clamped}%`}>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--surface-3)" strokeWidth={stroke} fill="transparent" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="url(#spaceRingGradient)"
          strokeWidth={stroke}
          fill="transparent"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - (clamped / 100) * circumference }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
        />
        <defs>
          <linearGradient id="spaceRingGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent-teal)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute text-center">
        <p className="font-mono-numbers text-2xl font-bold text-[var(--text-primary)]">{clamped}%</p>
        <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">Progress</p>
      </div>
    </div>
  )
}

/** Optional visual customization: an accent colour set on the Space. */
function SpaceAccentBar({ accent }) {
  if (!accent) return null
  return (
    <span
      aria-hidden="true"
      title={`Space accent ${accent}`}
      className="mt-3 block h-1 w-24 rounded-full"
      style={{ background: `linear-gradient(90deg, ${accent}, transparent)` }}
    />
  )
}

export default function SpaceDashboard({ spaceId, onOpenProject, onOpenWorkspace }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function load() {
    if (!spaceId) return
    setLoading(true)
    setError('')
    try {
      setData(await getSpaceAnalytics(spaceId))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId])

  const projects = useMemo(
    () => [...(data?.projects ?? [])].sort((a, b) => (a.overall_progress ?? 101) - (b.overall_progress ?? 101)),
    [data],
  )
  const attention = data?.areas_requiring_attention ?? []
  const activity = (data?.activity ?? []).filter((item) => item.type !== 'mastery_updated').slice(0, 8)

  if (!spaceId) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6">
        <EmptyState icon={Boxes} title="No Space selected" description="Pick a Space to see its projects and progress." />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={Compass}
        title={data?.space?.name || 'Space Overview'}
        subtitle={
          data?.space?.description ||
          'A high-level view of this Space: its projects, recent activity, overall progress and the areas needing attention.'
        }
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
        <SpaceAccentBar accent={data?.space?.accent} />
      </PageHeader>

      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          {error}
        </p>
      )}

      {loading && !data ? (
        <LoadingBlock label="Loading space overview" rows={4} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Projects" value={data?.projects_count ?? 0} icon={FolderKanban} tone="accent" hint="In this Space" />
            <StatCard label="Materials" value={data?.documents_count ?? 0} icon={FileText} tone="blue" hint="Indexed documents" />
            <StatCard
              label="Areas needing attention"
              value={attention.length}
              icon={Target}
              tone={attention.length ? 'danger' : 'success'}
              hint={attention.length ? 'Concepts below the mastery band' : 'Nothing flagged right now'}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div className="space-y-6">
              <Panel title="Overall progress" subtitle="Average concept mastery across this Space" icon={Activity}>
                <div className="flex flex-col items-center gap-5 sm:flex-row">
                  <ProgressRing value={data?.overall_progress ?? 0} />
                  <div className="w-full space-y-2">
                    {data?.overall_progress == null ? (
                      <p className="text-xs leading-relaxed text-[var(--text-muted)]">
                        No mastery evidence yet. Open a project and complete a quiz or an assessment to start measuring
                        progress.
                      </p>
                    ) : (
                      <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                        Averaged across {projects.filter((project) => project.overall_progress != null).length} project
                        {projects.length === 1 ? '' : 's'} with evidence. Mastery is an estimate — it moves as new
                        quizzes and assessments add evidence.
                      </p>
                    )}
                  </div>
                </div>
              </Panel>

              <Panel title="Areas requiring attention" subtitle="Weakest concepts across this Space" icon={Target}>
                {attention.length === 0 ? (
                  <EmptyState
                    icon={Sparkles}
                    title="Nothing needs attention"
                    description="No concept in this Space is currently below the mastery band. Keep practising to confirm it holds."
                  />
                ) : (
                  <ul className="space-y-4">
                    {attention.map((row) => (
                      <li key={`${row.project_id}-${row.concept}`} className="space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="flex min-w-0 items-center gap-2">
                            <GrowthBadge classification="needs_attention" />
                            <span className="truncate text-xs font-medium text-[var(--text-primary)]">{row.concept}</span>
                          </span>
                          <button
                            type="button"
                            onClick={() => onOpenProject?.(row.project_id, 'assessment')}
                            className="inline-flex shrink-0 items-center gap-1 text-[10px] font-semibold text-[var(--accent)] transition hover:text-[var(--accent-strong)]"
                          >
                            Assess <ArrowUpRight className="size-3" />
                          </button>
                        </div>
                        <MasteryBar concept={row.project_title} score={row.score} tone="danger" />
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>

            <div className="space-y-6">
              <Panel title="Projects" subtitle="Weakest first, so the next move is obvious" icon={FolderKanban}>
                {projects.length === 0 ? (
                  <EmptyState icon={Layers} title="No projects yet" description="Create a project in this Space to start learning." />
                ) : (
                  <ul className="space-y-3">
                    {projects.map((project) => (
                      <li key={project.id}>
                        <button
                          type="button"
                          onClick={() => onOpenProject?.(project.id, 'project-dashboard')}
                          className="group w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-3.5 text-left transition hover:border-[var(--accent)]/40 hover:bg-[var(--surface-2)]"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate font-display text-sm font-semibold text-[var(--text-primary)]">
                                {project.title}
                              </p>
                              <p className="mt-0.5 line-clamp-1 text-[11px] text-[var(--text-muted)]">
                                {project.description || project.learning_goal || 'No description yet'}
                              </p>
                            </div>
                            <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-[var(--text-muted)] transition group-hover:text-[var(--accent)]" />
                          </div>

                          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                            <span className="inline-flex items-center gap-1">
                              <FileText className="size-3" /> {project.documents} material{project.documents === 1 ? '' : 's'}
                            </span>
                            <span className="inline-flex items-center gap-1">
                              <Target className="size-3" /> {project.concepts_tracked} concept{project.concepts_tracked === 1 ? '' : 's'}
                            </span>
                            {project.latest_activity && <span>{relativeTime(project.latest_activity.created_at)}</span>}
                          </div>

                          {project.overall_progress == null ? (
                            <p className="mt-2.5 text-[11px] text-[var(--text-muted)]">No mastery evidence yet</p>
                          ) : (
                            <div className="mt-2.5">
                              <MasteryBar
                                concept={
                                  project.weakest_concept ? `Weakest: ${project.weakest_concept}` : 'Project mastery'
                                }
                                score={project.overall_progress}
                                animate={false}
                              />
                            </div>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              <Panel title="Recent activity" subtitle="Across the projects in this Space" icon={Activity}>
                {activity.length === 0 ? (
                  <EmptyState icon={Activity} title="No activity yet" description="Uploads, tutor turns, quizzes and assessments appear here." />
                ) : (
                  <ul className="divide-y divide-[var(--border)]">
                    {activity.map((item) => {
                      const meta = describeEvent(item.type)
                      return (
                        <ActivityItem
                          key={item.id}
                          label={meta.label}
                          detail={item.payload?.filename || item.payload?.title || item.payload?.topic || item.payload?.concept || null}
                          timestamp={relativeTime(item.created_at)}
                          icon={meta.icon}
                          tone={meta.tone}
                        />
                      )
                    })}
                  </ul>
                )}
              </Panel>

              <button
                type="button"
                onClick={() => onOpenWorkspace?.('global-analytics')}
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] px-4 py-3 text-left text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)]"
              >
                See cross-project trends in Global Analytics
                <ArrowUpRight className="ml-1 inline size-3" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
