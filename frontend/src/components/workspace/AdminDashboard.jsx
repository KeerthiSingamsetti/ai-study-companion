import { useEffect, useState } from 'react'
import {
  Activity,
  BarChart3,
  Cpu,
  FileText,
  FolderKanban,
  Gauge,
  RefreshCw,
  ServerCog,
  Shield,
  Users,
} from 'lucide-react'
import { getAdminOperations, getAdminProduct } from '../../api/client'
import { BarChart, EmptyState, JobStatePill, LoadingBlock, PageHeader, Panel, StatCard } from '../ui/primitives'
import { describeEvent } from '../../lib/learning'

const PIPELINE_STATES = ['queued', 'processing', 'ready', 'failed']

export default function AdminDashboard() {
  const [operations, setOperations] = useState(null)
  const [product, setProduct] = useState(null)
  const [error, setError] = useState('')
  const [forbidden, setForbidden] = useState(false)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    setForbidden(false)
    try {
      const [ops, prod] = await Promise.all([getAdminOperations(), getAdminProduct()])
      setOperations(ops)
      setProduct(prod)
    } catch (err) {
      if (err.status === 401 || err.status === 403) setForbidden(true)
      else setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (forbidden) {
    return (
      <div className="mx-auto w-full max-w-3xl p-6">
        <EmptyState
          icon={Shield}
          title="Administrator access required"
          description="This console is limited to accounts with the admin role. The API enforces this independently of the UI — a non-admin session cannot read these endpoints."
        />
      </div>
    )
  }

  const ingestion = operations?.ingestion ?? {}
  const aiCalls = operations?.ai_calls ?? {}
  const jobsTotal = PIPELINE_STATES.reduce((sum, state) => sum + (ingestion[state] ?? 0), 0)
  const failedJobs = ingestion.failed ?? 0
  const failedCalls = aiCalls.failed ?? 0
  const callsTotal = aiCalls.total ?? 0
  const successRate = callsTotal > 0 ? Math.round(((callsTotal - failedCalls) / callsTotal) * 100) : null

  const eventRows = Object.entries(product?.event_counts ?? {})
    .map(([type, value]) => ({ label: describeEvent(type).label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={Shield}
        title="Admin Operations Console"
        subtitle="Platform users, background processing, AI usage and system health."
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
        <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
          {error}
        </p>
      )}

      {loading && !operations ? (
        <LoadingBlock label="Loading admin operations" rows={5} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Users" value={operations?.users ?? 0} icon={Users} tone="accent" hint="Registered accounts" />
            <StatCard label="Projects" value={product?.projects ?? 0} icon={FolderKanban} tone="teal" hint="With indexed material" />
            <StatCard label="Documents" value={product?.documents ?? 0} icon={FileText} tone="blue" hint="Stored materials" />
            <StatCard
              label="AI calls"
              value={callsTotal}
              icon={Cpu}
              tone={failedCalls ? 'warning' : 'success'}
              hint={failedCalls ? `${failedCalls} failed` : 'All calls succeeded'}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <Panel title="System health" subtitle="Model layer and job pipeline status" icon={Gauge}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Avg AI latency
                  </p>
                  <p className="mt-1.5 font-mono-numbers text-xl font-bold text-[var(--text-primary)]">
                    {aiCalls.avg_latency_ms == null ? '—' : `${Math.round(aiCalls.avg_latency_ms)} ms`}
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    AI success rate
                  </p>
                  <p
                    className={`mt-1.5 font-mono-numbers text-xl font-bold ${
                      successRate == null
                        ? 'text-[var(--text-primary)]'
                        : successRate >= 95
                          ? 'text-[var(--success)]'
                          : successRate >= 85
                            ? 'text-[var(--warning)]'
                            : 'text-[var(--danger)]'
                    }`}
                  >
                    {successRate == null ? '—' : `${successRate}%`}
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Ingestion jobs
                  </p>
                  <p className="mt-1.5 font-mono-numbers text-xl font-bold text-[var(--text-primary)]">{jobsTotal}</p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Failed jobs
                  </p>
                  <p className={`mt-1.5 font-mono-numbers text-xl font-bold ${failedJobs ? 'text-[var(--danger)]' : 'text-[var(--success)]'}`}>
                    {failedJobs}
                  </p>
                </div>
              </div>

              <div className="mt-5 border-t border-[var(--border)] pt-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Pipeline states
                </p>
                <div className="mt-2.5 flex flex-wrap gap-2">
                  {PIPELINE_STATES.map((state) => (
                    <span key={state} className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-2.5 py-1">
                      <JobStatePill state={state} />
                      <span className="font-mono-numbers text-xs font-bold text-[var(--text-primary)]">
                        {ingestion[state] ?? 0}
                      </span>
                    </span>
                  ))}
                </div>
              </div>
            </Panel>

            <div className="space-y-6">
              <Panel title="Background processing" subtitle="Material ingestion by state" icon={ServerCog}>
                {jobsTotal === 0 ? (
                  <EmptyState icon={ServerCog} title="No ingestion jobs" description="Jobs appear as material is uploaded across the platform." />
                ) : (
                  <BarChart
                    tone="teal"
                    data={PIPELINE_STATES.map((state) => ({
                      label: state,
                      value: ingestion[state] ?? 0,
                    }))}
                  />
                )}
              </Panel>

              <Panel title="Learning-loop activity" subtitle="Platform event distribution" icon={BarChart3}>
                {eventRows.length === 0 ? (
                  <EmptyState icon={Activity} title="No events recorded" description="Learning events appear here as users study." />
                ) : (
                  <BarChart data={eventRows} tone="blue" />
                )}
              </Panel>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed text-[var(--text-muted)]">
            This console is a lightweight operational view over the same event, job and AI-call records the product
            writes — it is intentionally not a replacement for infrastructure monitoring. Per-user learning journeys
            remain visible to that user only.
          </p>
        </>
      )}
    </div>
  )
}
