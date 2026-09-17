import { RefreshCw } from 'lucide-react'

export const Metric = ({ label, value }) => <div className="rounded-xl border border-white/10 bg-white/[.03] p-4"><p className="text-xs text-[var(--text-muted)]">{label}</p><p className="mt-2 text-2xl font-bold text-white">{value ?? '—'}</p></div>

export const ActivityList = ({ items = [] }) => <section className="mt-6 rounded-xl border border-white/10 bg-white/[.03] p-5"><h2 className="font-semibold text-white">Recent activity</h2><div className="mt-3 space-y-2">{items.length ? items.map(item => <div key={item.id} className="flex justify-between border-b border-white/5 py-2 text-sm"><span className="capitalize text-[var(--text-secondary)]">{item.type.replaceAll('_', ' ')}</span><span className="text-xs text-[var(--text-muted)]">{new Date(item.created_at).toLocaleString()}</span></div>) : <p className="text-sm text-[var(--text-muted)]">Activity will appear as you study.</p>}</div></section>

export default function AnalyticsLayout({ title, subtitle, loading, error, onRefresh, children }) {
  return <div className="h-full w-full overflow-y-auto p-6 text-[var(--text-primary)] max-w-5xl mx-auto"><div className="flex items-center justify-between border-b border-white/10 pb-5"><div><h1 className="text-xl font-bold text-white">{title}</h1><p className="mt-1 text-sm text-[var(--text-muted)]">{subtitle}</p></div><button onClick={onRefresh} className="rounded-lg border border-white/10 p-2" title="Refresh"><RefreshCw className="size-4" /></button></div>{error && <p className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}{loading ? <p className="mt-8 text-sm text-[var(--text-muted)]">Loading analytics…</p> : children}</div>
}
