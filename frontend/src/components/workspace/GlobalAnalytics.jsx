import { useEffect, useState } from 'react'
import { BarChart3, Cpu, FolderKanban, Gauge, Globe2, RefreshCw, TrendingUp } from 'lucide-react'
import { getGlobalAnalytics } from '../../api/client'
import { BarChart, EmptyState, LoadingBlock, PageHeader, Panel, StatCard } from '../ui/primitives'
import { describeEvent } from '../../lib/learning'

export default function GlobalAnalytics() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setData(await getGlobalAnalytics())
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

  const activityRows = Object.entries(data?.activity_by_type ?? {})
    .map(([type, value]) => ({ label: describeEvent(type).label, value }))
    .sort((a, b) => b.value - a.value)

  const successRate = data?.ai_success_rate
  const failedCalls =
    successRate == null || data?.ai_calls == null
      ? null
      : Math.round((data.ai_calls * (100 - successRate)) / 100)

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6 text-[var(--text-primary)]">
      <PageHeader
        icon={Globe2}
        title="Global Analytics"
        subtitle={`Cross-project learning trends over the last ${data?.period_days ?? 7} days.`}
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

      {loading && !data ? (
        <LoadingBlock label="Loading global analytics" rows={4} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Projects" value={data?.projects ?? 0} icon={FolderKanban} tone="accent" hint="Across all Spaces" />
            <StatCard label="AI calls" value={data?.ai_calls ?? 0} icon={Cpu} tone="blue" hint="Model requests logged" />
            <StatCard
              label="AI success rate"
              value={successRate == null ? '—' : `${successRate}%`}
              icon={Gauge}
              tone={successRate == null ? 'accent' : successRate >= 95 ? 'success' : successRate >= 85 ? 'warning' : 'danger'}
              hint={failedCalls == null ? 'No calls yet' : `~${failedCalls} failed`}
            />
            <StatCard
              label="Tracked events"
              value={activityRows.reduce((sum, row) => sum + row.value, 0)}
              icon={TrendingUp}
              tone="teal"
              hint={`Last ${data?.period_days ?? 7} days`}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <Panel
              title="Activity by type"
              subtitle="How your learning loop is being used"
              icon={BarChart3}
            >
              {activityRows.length === 0 ? (
                <EmptyState
                  icon={BarChart3}
                  title="No activity in this window"
                  description="Upload material, ask the Tutor a question, or take a quiz and this chart fills in."
                />
              ) : (
                <BarChart data={activityRows} />
              )}
            </Panel>

            <div className="space-y-6">
              <Panel title="AI observability" subtitle="Reliability of the model layer" icon={Cpu}>
                <dl className="space-y-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-[var(--text-secondary)]">Requests logged</dt>
                    <dd className="font-mono-numbers font-semibold text-[var(--text-primary)]">{data?.ai_calls ?? 0}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-[var(--text-secondary)]">Success rate</dt>
                    <dd className="font-mono-numbers font-semibold text-[var(--text-primary)]">
                      {successRate == null ? '—' : `${successRate}%`}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-[var(--text-secondary)]">Failed requests (est.)</dt>
                    <dd className="font-mono-numbers font-semibold text-[var(--text-primary)]">{failedCalls ?? '—'}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-[var(--text-secondary)]">Window</dt>
                    <dd className="font-mono-numbers font-semibold text-[var(--text-primary)]">
                      Last {data?.period_days ?? 7} days
                    </dd>
                  </div>
                </dl>
                <p className="mt-4 border-t border-[var(--border)] pt-3 text-[11px] leading-relaxed text-[var(--text-muted)]">
                  Every Tutor, quiz, assessment and recommendation call is recorded with model, latency, tokens and
                  cost in the AI call log; failures are surfaced here rather than hidden.
                </p>
              </Panel>

              <Panel title="How to read this" icon={Globe2}>
                <ul className="space-y-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                  <li className="flex gap-2">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--accent)]" />
                    Activity counts come from the idempotent learning event log, not UI estimates.
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--accent-teal)]" />
                    All figures are scoped to your own account and projects.
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--accent-blue)]" />
                    Platform-wide and per-user operational views live in the Admin console for administrators.
                  </li>
                </ul>
              </Panel>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
