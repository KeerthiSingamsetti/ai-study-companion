import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  BookOpen,
  FolderKanban,
  Lightbulb,
  MessageSquare,
  Play,
  RefreshCw,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { getHomeAnalytics, getProjectAnalytics } from '../../api/client'
import { useWorkspace } from '../../context/WorkspaceContext'
import {
  ActivityItem,
  EmptyState,
  LoadingBlock,
  MasteryBar,
  PageHeader,
  Panel,
  RecommendationCard,
  StatCard,
} from '../ui/primitives'
import { LEARNING_STEPS, describeEvent, rankMastery, relativeTime } from '../../lib/learning'

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export default function HomeDashboard({ user, onOpenProject }) {
  const { setActiveWorkspace } = useWorkspace()
  const [data, setData] = useState(null)
  const [masteryByProject, setMasteryByProject] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const home = await getHomeAnalytics()
      setData(home)

      // Aggregate concept mastery across the most recent projects so the
      // home view can answer "what needs attention?" without a new endpoint.
      const recent = (home.projects ?? []).slice(0, 3)
      const results = await Promise.allSettled(recent.map((project) => getProjectAnalytics(project.id)))
      const rows = []
      results.forEach((result, index) => {
        if (result.status !== 'fulfilled') return
        const project = recent[index]
        for (const concept of result.value?.mastery ?? []) {
          rows.push({ ...concept, projectId: project.id, projectTitle: project.title })
        }
      })
      setMasteryByProject(rows)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const continueProject = data?.projects?.[0] ?? null
  const attention = useMemo(() => rankMastery(masteryByProject).filter((row) => (row.score ?? 100) < 75).slice(0, 4), [masteryByProject])
  const recommendations = data?.recommendations ?? []
  const activity = data?.recent_activity ?? []

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={Sparkles}
        title={`${greeting()}${user?.display_name ? `, ${user.display_name.split(' ')[0]}` : ''}`}
        subtitle="Where you were, how you are doing, and what to do next."
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
        {/* Learning loop strip — makes the product's spine visible */}
        <ol className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1.5">
          {LEARNING_STEPS.map((step, index) => (
            <li key={step.id} className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                <step.icon className="size-3 text-[var(--accent)]" />
                {step.label}
              </span>
              {index < LEARNING_STEPS.length - 1 && <span className="text-[var(--text-muted)]">→</span>}
            </li>
          ))}
        </ol>
      </PageHeader>

      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          {error}
        </p>
      )}

      {loading && !data ? (
        <LoadingBlock label="Loading your dashboard" rows={4} />
      ) : (
        <>
          {/* ── Continue learning hero ─────────────────────────────── */}
          {continueProject ? (
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card edge-highlight relative overflow-hidden rounded-[var(--radius-card)] p-6"
            >
              <div className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-[var(--accent)]/10 blur-3xl" />
              <div className="relative flex flex-wrap items-end justify-between gap-5">
                <div className="min-w-0">
                  <span className="inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--accent)]">
                    <Play className="size-3" /> Continue learning
                  </span>
                  <h2 className="mt-3 truncate font-display text-2xl font-bold tracking-tight text-[var(--text-primary)]">
                    {continueProject.title}
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Last activity {relativeTime(continueProject.updated_at) || 'recently'} · pick up the conversation with your AI Tutor.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => onOpenProject?.(continueProject.id, 'chat')}
                    className="inline-flex items-center gap-2 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-2.5 text-xs font-bold text-[#1A1405] shadow-[var(--glow-accent)] transition hover:bg-[var(--accent-strong)]"
                  >
                    <MessageSquare className="size-3.5" /> Resume with Tutor
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpenProject?.(continueProject.id, 'project-dashboard')}
                    className="inline-flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-1)] px-4 py-2.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
                  >
                    View analytics <ArrowRight className="size-3.5" />
                  </button>
                </div>
              </div>
            </motion.section>
          ) : (
            <EmptyState
              icon={BookOpen}
              title="No projects yet"
              description="Create a Space and a Project, upload a PDF, and your learning loop begins here."
            />
          )}

          {/* ── Metric tiles ───────────────────────────────────────── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Projects" value={data?.projects_count ?? 0} icon={FolderKanban} tone="accent" hint="Across all Spaces" />
            <StatCard label="Materials" value={data?.documents_count ?? 0} icon={BookOpen} tone="blue" hint="Indexed PDFs" />
            <StatCard label="Recommendations" value={recommendations.length} icon={Lightbulb} tone="success" hint="Open next actions" />
            <StatCard label="Tracked concepts" value={masteryByProject.length} icon={Target} tone="teal" hint="With mastery evidence" />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
            <div className="space-y-6">
              {/* ── Recommended next actions ───────────────────────── */}
              <Panel
                title="Recommended next actions"
                subtitle="Generated from your mastery, mistakes and recent activity"
                icon={Lightbulb}
              >
                {recommendations.length === 0 ? (
                  <EmptyState
                    icon={Target}
                    title="No open recommendations"
                    description="Take a quiz or an assessment and the system will surface what to work on next."
                  />
                ) : (
                  <ul className="space-y-3">
                    {recommendations.map((item) => (
                      <li key={item.id}>
                        <RecommendationCard
                          text={item.text}
                          trigger={item.trigger}
                          action="Open project"
                          onAction={item.project_id ? () => onOpenProject?.(item.project_id, 'chat') : undefined}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              {/* ── Recent projects ────────────────────────────────── */}
              <Panel title="Recent projects" icon={FolderKanban} subtitle="Jump back into a workspace">
                {(data?.projects ?? []).length === 0 ? (
                  <EmptyState icon={FolderKanban} title="No projects yet" description="Projects live inside Spaces and hold your materials and mastery." />
                ) : (
                  <ul className="grid gap-3 sm:grid-cols-2">
                    {data.projects.slice(0, 4).map((project) => (
                      <li key={project.id}>
                        <button
                          type="button"
                          onClick={() => onOpenProject?.(project.id, 'project-dashboard')}
                          className="group w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] p-4 text-left transition hover:border-[var(--accent)]/40 hover:bg-[var(--surface-2)]"
                        >
                          <span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                            <FolderKanban className="size-3" /> Project
                          </span>
                          <span className="mt-1.5 block truncate font-display text-sm font-semibold text-[var(--text-primary)]">
                            {project.title}
                          </span>
                          <span className="mt-1 block text-xs text-[var(--text-muted)]">
                            Updated {relativeTime(project.updated_at) || 'recently'}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>

            <div className="space-y-6">
              {/* ── Areas requiring attention ──────────────────────── */}
              <Panel
                title="Areas requiring attention"
                subtitle="Weakest concepts across your recent projects"
                icon={TrendingDown}
                action={
                  <button
                    type="button"
                    onClick={() => setActiveWorkspace('progress')}
                    className="text-[11px] font-semibold text-[var(--accent)] transition hover:text-[var(--accent-strong)]"
                  >
                    Full progress →
                  </button>
                }
              >
                {attention.length === 0 ? (
                  <EmptyState
                    icon={TrendingUp}
                    title="Nothing flagged right now"
                    description="Concepts drop here when mastery evidence falls below the attention band."
                  />
                ) : (
                  <ul className="space-y-4">
                    {attention.map((row) => (
                      <li key={`${row.projectId}-${row.concept}`}>
                        <MasteryBar concept={`${row.concept}`} score={row.score} attempts={row.attempts} />
                        <button
                          type="button"
                          onClick={() => onOpenProject?.(row.projectId, 'progress')}
                          className="mt-1.5 text-[11px] font-medium text-[var(--text-muted)] transition hover:text-[var(--accent)]"
                        >
                          {row.projectTitle} · view breakdown →
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              {/* ── Activity feed ─────────────────────────────────── */}
              <Panel title="Recent activity" subtitle="Event-driven learning history" icon={TrendingUp}>
                {activity.length === 0 ? (
                  <EmptyState icon={Sparkles} title="No activity yet" description="Uploads, tutor turns, quizzes and assessments appear here." />
                ) : (
                  <ul className="divide-y divide-[var(--border)]">
                    {activity.slice(0, 8).map((item) => {
                      const meta = describeEvent(item.type)
                      return (
                        <ActivityItem
                          key={item.id}
                          label={meta.label}
                          detail={item.payload?.filename || item.payload?.title || null}
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
