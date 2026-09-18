import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Brain,
  CalendarRange,
  Cpu,
  Eye,
  FileText,
  Filter,
  FolderKanban,
  Gauge,
  GraduationCap,
  RefreshCw,
  Search,
  ServerCog,
  Shield,
  SquarePen,
  Users,
  X,
} from 'lucide-react'
import {
  getAdminActivity,
  getAdminActivityFilters,
  getAdminActivityTypes,
  getAdminAiUsage,
  getAdminEvaluation,
  getAdminJobs,
  getAdminOperations,
  getAdminProduct,
  getAdminSpaces,
  getAdminUser,
  getAdminUsers,
  getAdminProjects,
} from '../../api/client'
import { BarChart, EmptyState, JobStatePill, LoadingBlock, MasteryBar, PageHeader, Panel, StatCard } from '../ui/primitives'
import { describeEvent, relativeTime } from '../../lib/learning'
import { Logo } from '../ui/primitives'

/* ────────────────────────────────────────────────────────────────
   Dedicated Admin Console — the entire app an admin sees.

   Deliberate product decision (documented in ASSUMPTIONS.md): the PRD
   frames the admin role purely as inspection/oversight (§16 uses only
   inspect/view/filter verbs), so admins get a management interface and
   never the student learning UI. Inspecting a user happens here, as a
   read-only panel over that user's data — not as the admin's own live
   Tutor/Quiz session.
   ──────────────────────────────────────────────────────────────── */

const SECTIONS = [
  { id: 'overview', label: 'System Health', icon: Gauge, description: 'Platform snapshot and job pipeline' },
  { id: 'users', label: 'Users', icon: Users, description: 'Accounts, rollups and journey inspection' },
  { id: 'spaces', label: 'Spaces', icon: GraduationCap, description: 'Every Space with owner and size' },
  { id: 'projects', label: 'Projects', icon: FolderKanban, description: 'Every Project, filterable by Space' },
  { id: 'activity', label: 'Activity', icon: CalendarRange, description: 'Platform event feed with filters' },
  { id: 'ai-usage', label: 'AI Usage', icon: Cpu, description: 'Calls, latency, tokens and cost by feature and model' },
  { id: 'ai-evaluation', label: 'AI Evaluation', icon: Brain, description: 'Live groundedness from retrieval traces' },
  { id: 'jobs', label: 'Background Jobs', icon: ServerCog, description: 'Ingestion pipeline with retries and errors' },
]

const fieldClass =
  'rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent)]/60'

/* ── Read-only user inspector (PRD §16) ──────────────────────────── */

function UserInspectorPanel({ userId, onClose }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async loader, same pattern as every workspace
    setLoading(true)
    getAdminUser(userId)
      .then((data) => {
        if (alive) setDetail(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [userId])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="User inspector">
      <button type="button" aria-label="Close inspector" className="absolute inset-0 cursor-default" onClick={onClose} />
      <div className="glass-panel relative my-auto max-h-[86vh] w-full max-w-4xl overflow-y-auto rounded-[var(--radius-card)] border border-[var(--border)] p-6 shadow-[var(--shadow-pop)]">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              <Eye className="size-3" /> Learner inspection
            </p>
            <h2 className="mt-1 truncate font-display text-lg font-bold text-[var(--text-primary)]">
              {detail?.user?.display_name ?? 'Loading…'}
            </h2>
            <p className="truncate text-xs text-[var(--text-muted)]">
              {detail?.user?.email} · {detail?.user?.role}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius-pill)] border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
          >
            <ArrowLeft className="size-3.5" /> Close
          </button>
        </div>

        {loading && <LoadingBlock label="Loading user journey" rows={4} />}
        {error && (
          <p role="alert" className="mt-4 rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
            {error}
          </p>
        )}

        {detail && (
          <div className="mt-5 space-y-5">
            <div className="grid grid-cols-4 gap-3">
              <StatCard label="Spaces" value={detail.spaces.length} />
              <StatCard label="Projects" value={detail.projects.length} />
              <StatCard
                label="AI calls"
                value={detail.ai_usage.calls}
                tone={detail.ai_usage.failed ? 'warning' : 'success'}
                hint={detail.ai_usage.failed ? `${detail.ai_usage.failed} failed` : `${detail.ai_usage.avg_latency_ms} ms avg`}
              />
              <StatCard
                label="Concepts"
                value={detail.mastery.length}
                tone="blue"
                hint="Tracked by evidence"
              />
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Projects" icon={FolderKanban}>
              {detail.projects.length === 0 ? (
                <EmptyState icon={FolderKanban} title="No projects" description="This account has not created a Project yet." />
              ) : (
                <ul className="space-y-2">
                  {detail.projects.map((project) => (
                    <li key={project.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5">
                      <p className="truncate text-xs font-semibold text-[var(--text-primary)]">{project.title}</p>
                      {project.learning_goal && (
                        <p className="mt-0.5 truncate text-[11px] text-[var(--text-muted)]">Goal: {project.learning_goal}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Recent activity" icon={Activity}>
              {detail.activity.length === 0 ? (
                <EmptyState icon={Activity} title="No events" description="Learning events appear here as this user studies." />
              ) : (
                <ul className="max-h-72 overflow-y-auto pr-1">
                  {detail.activity.slice(0, 12).map((event) => (
                    <li key={event.id} className="flex items-center justify-between gap-3 border-b border-[var(--border)] py-2 last:border-0">
                      <span className="truncate text-xs capitalize text-[var(--text-primary)]">
                        {describeEvent(event.type).label}
                      </span>
                      <span className="shrink-0 text-[11px] text-[var(--text-muted)]">{relativeTime(event.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Concept mastery" subtitle="Lowest twelve concepts" icon={Brain}>
              {detail.mastery.length === 0 ? (
                <EmptyState icon={Brain} title="No mastery tracked" description="Mastery appears once this user takes quizzes or assessments." />
              ) : (
                <div className="space-y-3">
                  {detail.mastery.map((row) => (
                    <MasteryBar key={row.concept} concept={row.concept} score={row.score} attempts={row.attempts} />
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Recent assessments" subtitle="Open-ended grading history" icon={SquarePen}>
              {detail.assessments.length === 0 ? (
                <EmptyState icon={SquarePen} title="No assessments" description="Graded written answers appear here." />
              ) : (
                <ul className="space-y-2.5">
                  {detail.assessments.map((item) => (
                    <li key={item.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5">
                      <p className="line-clamp-2 text-xs text-[var(--text-primary)]">{item.question}</p>
                      <p className="mt-1.5 font-mono-numbers text-[11px] text-[var(--text-muted)]">
                        understanding {Math.round(item.understanding)}% · accuracy {Math.round(item.accuracy)}% · {relativeTime(item.created_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            </div>

            <p className="text-[11px] leading-relaxed text-[var(--text-muted)]">
              Everything above is {detail.user.display_name}&apos;s own data. Nothing here opens a Tutor, Quiz or
              Flashcard session on their behalf.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Section bodies ─────────────────────────────────────────────── */

function OverviewSection() {
  const [operations, setOperations] = useState(null)
  const [product, setProduct] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [ops, prod] = await Promise.all([getAdminOperations(), getAdminProduct()])
      setOperations(ops)
      setProduct(prod)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load() // eslint-disable-line react-hooks/set-state-in-effect -- async loader, same pattern as every workspace
  }, [])

  const ingestion = operations?.ingestion ?? {}
  const aiCalls = operations?.ai_calls ?? {}
  const failedCalls = aiCalls.failed ?? 0
  const callsTotal = aiCalls.total ?? 0
  const successRate = callsTotal > 0 ? Math.round(((callsTotal - failedCalls) / callsTotal) * 100) : null
  const eventRows = Object.entries(product?.event_counts ?? {})
    .map(([type, value]) => ({ label: describeEvent(type).label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Gauge}
        title="System health"
        subtitle="Platform snapshot, model layer and job pipeline."
        actions={
          <button type="button" onClick={load} className="inline-flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]">
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        }
      />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      {loading && !operations ? (
        <LoadingBlock rows={5} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Users" value={operations?.users ?? 0} icon={Users} tone="accent" hint="Registered accounts" />
            <StatCard label="Projects" value={product?.projects ?? 0} icon={FolderKanban} tone="teal" hint="With indexed material" />
            <StatCard label="Documents" value={product?.documents ?? 0} icon={FileText} tone="blue" hint="Stored materials" />
            <StatCard label="AI calls" value={callsTotal} icon={Cpu} tone={failedCalls ? 'warning' : 'success'} hint={failedCalls ? `${failedCalls} failed` : 'All calls succeeded'} />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Reliability" subtitle="Model layer and pipeline" icon={ServerCog}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Avg AI latency</p>
                  <p className="mt-1.5 font-mono-numbers text-xl font-bold text-[var(--text-primary)]">{aiCalls.avg_latency_ms == null ? '—' : `${Math.round(aiCalls.avg_latency_ms)} ms`}</p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">AI success rate</p>
                  <p className={`mt-1.5 font-mono-numbers text-xl font-bold ${successRate == null ? 'text-[var(--text-primary)]' : successRate >= 95 ? 'text-[var(--success)]' : successRate >= 85 ? 'text-[var(--warning)]' : 'text-[var(--danger)]'}`}>
                    {successRate == null ? '—' : `${successRate}%`}
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Failed jobs</p>
                  <p className="mt-1.5 font-mono-numbers text-xl font-bold text-[var(--text-primary)]">{ingestion.failed ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Pipeline</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {['queued', 'processing', 'ready', 'failed'].map((state) => (
                      <span key={state} className="inline-flex items-center gap-1.5">
                        <JobStatePill state={state} />
                        <span className="font-mono-numbers text-xs font-bold text-[var(--text-primary)]">{ingestion[state] ?? 0}</span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Panel>
            <Panel title="Learning-loop activity" subtitle="Platform event distribution" icon={BarChart3}>
              {eventRows.length === 0 ? (
                <EmptyState icon={Activity} title="No events recorded" description="Learning events appear as users study." />
              ) : (
                <BarChart data={eventRows} tone="blue" />
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}

function UsersSection() {
  const [users, setUsers] = useState(null)
  const [query, setQuery] = useState('')
  const [inspectedId, setInspectedId] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getAdminUsers(query ? { q: query } : {})
      .then((data) => {
        if (alive) setUsers(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [query])

  return (
    <div className="space-y-6">
      <PageHeader icon={Users} title="Users" subtitle="Every account with activity rollups. Open any learner's journey." />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      <Panel
        title="Accounts"
        subtitle={users ? `${users.total} registered · showing ${users.users.length}` : 'Loading…'}
        icon={Search}
        action={
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search email or name…"
            className={`${fieldClass} w-52`}
            aria-label="Search users"
          />
        }
      >
        {users === null ? (
          <LoadingBlock rows={5} />
        ) : users.users.length === 0 ? (
          <EmptyState icon={Users} title="No matching accounts" description="Try a different search." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-2 pr-3 font-semibold">User</th>
                  <th className="py-2 pr-3 font-semibold">Role</th>
                  <th className="py-2 pr-3 font-semibold">Spaces</th>
                  <th className="py-2 pr-3 font-semibold">Projects</th>
                  <th className="py-2 pr-3 font-semibold">Active 30d</th>
                  <th className="py-2 pr-3 font-semibold">AI calls</th>
                  <th className="py-2 font-semibold text-right">Journey</th>
                </tr>
              </thead>
              <tbody>
                {users.users.map((user) => (
                  <tr key={user.id} className="border-b border-[var(--border)]/50 last:border-0">
                    <td className="py-2 pr-3">
                      <p className="truncate font-semibold text-[var(--text-primary)]">{user.display_name}</p>
                      <p className="truncate text-[11px] text-[var(--text-muted)]">{user.email}</p>
                    </td>
                    <td className="py-2 pr-3">
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${user.role === 'admin' ? 'border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[var(--accent)]' : 'border-[var(--border)] text-[var(--text-muted)]'}`}>
                        {user.role}
                      </span>
                    </td>
                    <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{user.spaces_count}</td>
                    <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{user.projects_count}</td>
                    <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{user.active_projects_30d}</td>
                    <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{user.ai_calls}</td>
                    <td className="py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setInspectedId(user.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--accent)] transition hover:border-[var(--accent)]/40 hover:bg-[var(--accent-soft)]"
                      >
                        <Eye className="size-3" /> Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {inspectedId && <UserInspectorPanel userId={inspectedId} onClose={() => setInspectedId(null)} />}
    </div>
  )
}

function SpacesSection() {
  const [spaces, setSpaces] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getAdminSpaces()
      .then((data) => {
        if (alive) setSpaces(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader icon={GraduationCap} title="Spaces" subtitle="Every Space platform-wide, with owner and size." />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      <Panel title="All Spaces" subtitle={spaces ? `${spaces.total} total` : 'Loading…'} icon={GraduationCap}>
        {spaces === null ? (
          <LoadingBlock rows={4} />
        ) : spaces.spaces.length === 0 ? (
          <EmptyState icon={GraduationCap} title="No Spaces" description="Spaces appear as accounts create them." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-2 pr-3 font-semibold">Space</th>
                  <th className="py-2 pr-3 font-semibold">Owner</th>
                  <th className="py-2 pr-3 font-semibold">Projects</th>
                  <th className="py-2 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody>
                {spaces.spaces.map((space) => (
                  <tr key={space.id} className="border-b border-[var(--border)]/50 last:border-0">
                    <td className="py-2 pr-3">
                      <p className="flex items-center gap-2 truncate font-semibold text-[var(--text-primary)]">
                        {space.accent && <span className="size-2 shrink-0 rounded-full" style={{ background: space.accent }} />}
                        {space.name}
                      </p>
                      {space.description && <p className="truncate text-[11px] text-[var(--text-muted)]">{space.description}</p>}
                    </td>
                    <td className="py-2 pr-3 text-[var(--text-secondary)]">{space.owner}</td>
                    <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{space.projects_count}</td>
                    <td className="py-2 text-[11px] text-[var(--text-muted)]">{relativeTime(space.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

function ProjectsSection() {
  const [projects, setProjects] = useState(null)
  const [spaces, setSpaces] = useState([])
  const [spaceFilter, setSpaceFilter] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getAdminSpaces()
      .then((data) => setSpaces(data.spaces))
      .catch(() => setSpaces([]))
  }, [])

  useEffect(() => {
    let alive = true
    getAdminProjects(spaceFilter ? { space_id: spaceFilter } : {})
      .then((data) => {
        if (alive) setProjects(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [spaceFilter])

  return (
    <div className="space-y-6">
      <PageHeader icon={FolderKanban} title="Projects" subtitle="Every Project platform-wide, filterable by Space." />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      <Panel
        title="All Projects"
        subtitle={projects ? `${projects.total} total` : 'Loading…'}
        icon={FolderKanban}
        action={
          <select value={spaceFilter} onChange={(event) => setSpaceFilter(event.target.value)} className={fieldClass} aria-label="Filter by Space">
            <option value="">All Spaces</option>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
        }
      >
        {projects === null ? (
          <LoadingBlock rows={5} />
        ) : projects.projects.length === 0 ? (
          <EmptyState icon={FolderKanban} title="No Projects" description="Projects appear as users create them." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-2 pr-3 font-semibold">Project</th>
                  <th className="py-2 pr-3 font-semibold">Owner</th>
                  <th className="py-2 pr-3 font-semibold">Space</th>
                  <th className="py-2 pr-3 font-semibold">Documents</th>
                  <th className="py-2 font-semibold">Updated</th>
                </tr>
              </thead>
              <tbody>
                {projects.projects.map((project) => (
                  <tr key={project.id} className="border-b border-[var(--border)]/50 last:border-0">
                    <td className="py-2 pr-3">
                      <p className="truncate font-semibold text-[var(--text-primary)]">{project.title}</p>
                      {project.learning_goal && <p className="truncate text-[11px] text-[var(--text-muted)]">Goal: {project.learning_goal}</p>}
                    </td>
                    <td className="py-2 pr-3 text-[var(--text-secondary)]">{projects.owners[project.user_id] ?? project.user_id}</td>
                    <td className="py-2 pr-3 text-[var(--text-secondary)]">{project.space_id ? projects.space_names[project.space_id] ?? '—' : '—'}</td>
                    <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{project.documents}</td>
                    <td className="py-2 text-[11px] text-[var(--text-muted)]">{relativeTime(project.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

function ActivitySection() {
  const [rows, setRows] = useState(null)
  const [types, setTypes] = useState([])
  const [options, setOptions] = useState({ users: [], projects: [] })
  const [filters, setFilters] = useState({ user_id: '', event_type: '', project_id: '', days: '30' })
  const [error, setError] = useState('')

  useEffect(() => {
    getAdminActivityTypes()
      .then(setTypes)
      .catch(() => setTypes([]))
  }, [])

  // Pickers are populated by name — an operator never types an identifier.
  // Choosing an account also narrows the Project list to their Projects.
  useEffect(() => {
    let alive = true
    getAdminActivityFilters(filters.user_id ? { user_id: filters.user_id } : {})
      .then((data) => {
        if (alive) setOptions(data)
      })
      .catch(() => {
        if (alive) setOptions({ users: [], projects: [] })
      })
    return () => {
      alive = false
    }
  }, [filters.user_id])

  useEffect(() => {
    let alive = true
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''))
    getAdminActivity(params)
      .then((data) => {
        if (alive) setRows(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [filters])

  const setFilter = (key) => (event) =>
    setFilters((prev) =>
      key === 'user_id' ? { ...prev, user_id: event.target.value, project_id: '' } : { ...prev, [key]: event.target.value },
    )

  return (
    <div className="space-y-6">
      <PageHeader icon={CalendarRange} title="Activity" subtitle="Platform event feed — filter by user, type, Project or period." />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      <Panel title="Event feed" subtitle={rows ? `${rows.length} events in window` : 'Loading…'} icon={Filter}>
        {/* Filters get their own row: four controls will not fit beside the
            panel title without overlapping it. */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
            <select value={filters.user_id} onChange={setFilter('user_id')} className={`${fieldClass} max-w-[13rem]`} aria-label="Filter by user">
              <option value="">All users</option>
              {options.users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.label} · {user.email}
                </option>
              ))}
            </select>
            <select value={filters.event_type} onChange={setFilter('event_type')} className={fieldClass} aria-label="Filter by event type">
              <option value="">All types</option>
              {types.map((type) => (
                <option key={type} value={type}>
                  {describeEvent(type).label}
                </option>
              ))}
            </select>
            <select value={filters.project_id} onChange={setFilter('project_id')} className={`${fieldClass} max-w-[13rem]`} aria-label="Filter by project">
              <option value="">All Projects</option>
              {options.projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.label}
                  {project.space ? ` · ${project.space}` : ''}
                </option>
              ))}
            </select>
            <select value={filters.days} onChange={setFilter('days')} className={fieldClass} aria-label="Filter by period">
              {['1', '7', '30', '90', '365'].map((days) => (
                <option key={days} value={days}>
                  Last {days} {days === '1' ? 'day' : 'days'}
                </option>
              ))}
            </select>
        </div>
        {rows === null ? (
          <LoadingBlock rows={5} />
        ) : rows.length === 0 ? (
          <EmptyState icon={Search} title="No matching events" description="Adjust the filters to widen the window." />
        ) : (
          <ul className="max-h-[26rem] space-y-1 overflow-y-auto pr-1">
            {rows.map((row) => (
              <li key={row.id} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 hover:bg-[var(--surface-2)]">
                <span className="min-w-0 truncate text-xs capitalize text-[var(--text-primary)]">
                  {describeEvent(row.type).label}
                  {row.project && <span className="text-[var(--text-muted)]"> · {row.project}</span>}
                </span>
                <span className="flex shrink-0 items-center gap-2 text-[11px] text-[var(--text-muted)]">
                  <span className="truncate">{row.user}</span>
                  {relativeTime(row.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}

function AiUsageSection() {
  const [usage, setUsage] = useState(null)
  const [days, setDays] = useState('30')
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getAdminAiUsage({ days })
      .then((data) => {
        if (alive) setUsage(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [days])

  const money = (value) => (value == null ? '—' : value < 0.01 && value > 0 ? `<$0.01` : `$${value.toFixed(2)}`)

  const table = (rows, labelHeader, capitalizeLabel = true) => (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
            <th className="py-2 pr-3 font-semibold">{labelHeader}</th>
            <th className="py-2 pr-3 font-semibold">Calls</th>
            <th className="py-2 pr-3 font-semibold">Failed</th>
            <th className="py-2 pr-3 font-semibold">Avg latency</th>
            <th className="py-2 pr-3 font-semibold">Tokens (in/out)</th>
            <th className="py-2 font-semibold">Est. cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-[var(--border)]/50 last:border-0">
              <td className={`py-2 pr-3 font-semibold text-[var(--text-primary)] ${capitalizeLabel ? 'capitalize' : 'font-mono-numbers'}`}>
                {capitalizeLabel ? (row.name ?? 'unattributed').replace(/_/g, ' ') : row.name ?? 'unattributed'}
              </td>
              <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{row.calls}</td>
              <td className={`py-2 pr-3 font-mono-numbers ${row.failed ? 'text-[var(--danger)]' : 'text-[var(--text-secondary)]'}`}>{row.failed}</td>
              <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{Math.round(row.avg_latency_ms)} ms</td>
              <td className="py-2 pr-3 font-mono-numbers text-[var(--text-secondary)]">{row.input_tokens.toLocaleString()} / {row.output_tokens.toLocaleString()}</td>
              <td className="py-2 font-mono-numbers text-[var(--text-secondary)]">{money(row.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Cpu}
        title="AI usage"
        subtitle="Calls, latency, tokens and estimated cost by feature and model."
        actions={
          <select value={days} onChange={(event) => setDays(event.target.value)} className={fieldClass} aria-label="Period">
            {['7', '30', '90', '365'].map((option) => (
              <option key={option} value={option}>
                Last {option} days
              </option>
            ))}
          </select>
        }
      />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      {usage === null ? (
        <LoadingBlock rows={5} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Total calls" value={usage.total_calls} tone="accent" />
            <StatCard label="Failed" value={usage.total_failed} tone={usage.total_failed ? 'danger' : 'success'} />
            <StatCard label="Estimated cost" value={money(usage.total_cost_usd)} tone="teal" hint={`${usage.period_days} day window`} />
          </div>
          <Panel title="By feature" subtitle="Tutor, quiz generation, grading, recommendations…" icon={Cpu}>
            {usage.by_feature.length === 0 ? (
              <EmptyState icon={Cpu} title="No AI calls in window" />
            ) : (
              table(usage.by_feature, 'Feature')
            )}
          </Panel>
          <Panel title="By model" subtitle="Which model served which traffic" icon={Brain}>
            {usage.by_model.length === 0 ? (
              <EmptyState icon={Brain} title="No AI calls in window" />
            ) : (
              table(usage.by_model, 'Model', false)
            )}
          </Panel>
        </>
      )}
    </div>
  )
}

function AiEvaluationSection() {
  const [evaluation, setEvaluation] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getAdminEvaluation()
      .then((data) => {
        if (alive) setEvaluation(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader icon={Brain} title="AI evaluation" subtitle="Live groundedness signals from real retrieval traffic." />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      {evaluation === null ? (
        <LoadingBlock rows={4} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Retrieval traces" value={evaluation.retrieval.traces_window} tone="blue" hint="Latest 200" />
            <StatCard
              label="Grounded rate"
              value={evaluation.retrieval.grounded_rate == null ? '—' : `${evaluation.retrieval.grounded_rate}%`}
              tone={evaluation.retrieval.grounded_rate >= 80 ? 'success' : 'warning'}
              hint={`${evaluation.retrieval.grounded} grounded`}
            />
            <StatCard label="Tutor calls" value={evaluation.tutor_calls.window} tone="teal" hint={`${evaluation.tutor_calls.failed} failed · ${Math.round(evaluation.tutor_calls.avg_latency_ms)} ms avg`} />
          </div>
          <Panel title="How to read this" icon={Brain}>
            <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{evaluation.note}</p>
            <p className="mt-2 text-xs leading-relaxed text-[var(--text-muted)]">
              The curated suite covers tutor accuracy, groundedness, citations, refusal behaviour, retrieval quality,
              assessment grading and recommendation relevance (see backend/eval). This panel deliberately reports only
              live signals, never stale benchmark numbers.
            </p>
          </Panel>
        </>
      )}
    </div>
  )
}

function JobsSection() {
  const [jobs, setJobs] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getAdminJobs(statusFilter ? { status: statusFilter } : {})
      .then((data) => {
        if (alive) setJobs(data)
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
    return () => {
      alive = false
    }
  }, [statusFilter])

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ServerCog}
        title="Background jobs"
        subtitle="Ingestion pipeline: retries, failures and recovery state."
        actions={
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className={fieldClass} aria-label="Filter by state">
            <option value="">All states</option>
            {['queued', 'processing', 'ready', 'failed'].map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        }
      />
      {error && <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">{error}</p>}
      {jobs === null ? (
        <LoadingBlock rows={5} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            {Object.entries(jobs.states).map(([state, count]) => (
              <StatCard key={state} label={state} value={count} tone={state === 'failed' ? 'danger' : state === 'ready' ? 'success' : 'blue'} />
            ))}
          </div>
          <Panel title="Jobs" subtitle={`${jobs.jobs.length} shown (latest 100)`} icon={ServerCog}>
            {jobs.jobs.length === 0 ? (
              <EmptyState icon={ServerCog} title="No jobs" description="Jobs appear as material is uploaded." />
            ) : (
              <ul className="max-h-[26rem] space-y-2 overflow-y-auto pr-1">
                {jobs.jobs.map((job) => (
                  <li key={job.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-[var(--text-primary)]">{job.document_filename ?? job.document_id}</p>
                      {job.error && <p className="truncate text-[11px] text-[var(--danger)]">{job.error}</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-2.5">
                      {job.retry_count > 0 && (
                        <span className="font-mono-numbers text-[11px] text-[var(--text-muted)]">{job.retry_count} retries</span>
                      )}
                      <JobStatePill state={job.status} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}
    </div>
  )
}

/* ── Shell ──────────────────────────────────────────────────────── */

export default function AdminConsole({ user, logout }) {
  const [section, setSection] = useState('overview')

  return (
    <div className="app-aurora flex h-screen w-screen overflow-hidden">
      {/* Admin-only navigation — no student learning tools here. */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface-1)]/40 p-4">
        <div className="px-2 py-2">
          <Logo size={36} subtitle="Admin Console" />
        </div>

        <nav className="mt-4 flex-1 space-y-0.5 overflow-y-auto" aria-label="Admin sections">
          {SECTIONS.map((item) => {
            const Icon = item.icon
            const isActive = section === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setSection(item.id)}
                title={item.description}
                aria-current={isActive ? 'page' : undefined}
                className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[var(--text-primary)]'
                    : 'border border-transparent text-[var(--text-secondary)] hover:bg-white/[0.04] hover:text-[var(--text-primary)]'
                }`}
              >
                <span className={`grid size-6 shrink-0 place-items-center rounded-lg border ${isActive ? 'border-[var(--accent)]/40 bg-[var(--accent)]/15 text-[var(--accent)]' : 'border-transparent bg-white/[0.02] text-[var(--text-muted)]'}`}>
                  <Icon className="size-3.5" />
                </span>
                <span className="truncate">{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="border-t border-[var(--border)] pt-3">
          <div className="flex items-center justify-between gap-2 px-2">
            <span className="inline-flex min-w-0 items-center gap-2 text-xs text-[var(--text-secondary)]">
              <Shield className="size-3.5 shrink-0 text-[var(--accent)]" />
              <span className="truncate">{user.display_name}</span>
            </span>
            <button
              type="button"
              onClick={logout}
              className="shrink-0 rounded-lg border border-[var(--border)] px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] transition hover:text-[var(--text-primary)]"
            >
              <X className="size-3" /> Sign out
            </button>
          </div>
          <p className="mt-2 px-2 text-[10px] leading-relaxed text-[var(--text-muted)]">
            Inspect learners and platform activity.
          </p>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl p-6">
          {section === 'overview' && <OverviewSection />}
          {section === 'users' && <UsersSection />}
          {section === 'spaces' && <SpacesSection />}
          {section === 'projects' && <ProjectsSection />}
          {section === 'activity' && <ActivitySection />}
          {section === 'ai-usage' && <AiUsageSection />}
          {section === 'ai-evaluation' && <AiEvaluationSection />}
          {section === 'jobs' && <JobsSection />}
        </div>
      </main>
    </div>
  )
}
