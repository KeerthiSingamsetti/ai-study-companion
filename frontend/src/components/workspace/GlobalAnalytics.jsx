import { useEffect, useState } from 'react'
import { getGlobalAnalytics } from '../../api/client'
import AnalyticsLayout, { Metric } from './AnalyticsLayout'

export default function GlobalAnalytics() {
  const [data, setData] = useState(null); const [error, setError] = useState('')
  const load = async () => { try { setError(''); setData(await getGlobalAnalytics()) } catch (err) { setError(err.message) } }
  useEffect(() => { void load() }, [])
  return <AnalyticsLayout title="Global Analytics" subtitle="Cross-project learning trends for the last seven days." loading={!data && !error} error={error} onRefresh={load}>{data && <><div className="mt-6 grid gap-4 sm:grid-cols-3"><Metric label="Projects" value={data.projects} /><Metric label="AI calls" value={data.ai_calls} /><Metric label="AI success rate" value={data.ai_success_rate == null ? '—' : `${data.ai_success_rate}%`} /></div><section className="mt-6 rounded-xl border border-white/10 bg-white/[.03] p-5"><h2 className="font-semibold text-white">Activity by type</h2><div className="mt-3 flex flex-wrap gap-2">{Object.entries(data.activity_by_type || {}).map(([key, value]) => <span key={key} className="rounded-full bg-white/[.06] px-3 py-1 text-xs text-[var(--text-secondary)]">{key.replaceAll('_', ' ')} · {value}</span>)}</div></section></>}</AnalyticsLayout>
}
