import { useEffect, useState } from 'react'
import { getHomeAnalytics } from '../../api/client'
import AnalyticsLayout, { ActivityList, Metric } from './AnalyticsLayout'

export default function HomeDashboard() {
  const [data, setData] = useState(null); const [error, setError] = useState('')
  const load = async () => { try { setError(''); setData(await getHomeAnalytics()) } catch (err) { setError(err.message) } }
  useEffect(() => { void load() }, [])
  return <AnalyticsLayout title="Home Dashboard" subtitle="Your current study workload and next steps." loading={!data && !error} error={error} onRefresh={load}>{data && <><div className="mt-6 grid gap-4 sm:grid-cols-3"><Metric label="Projects" value={data.projects_count} /><Metric label="Documents" value={data.documents_count} /><Metric label="Recommendations" value={data.recommendations?.length} /></div><ActivityList items={data.recent_activity} /></>}</AnalyticsLayout>
}
