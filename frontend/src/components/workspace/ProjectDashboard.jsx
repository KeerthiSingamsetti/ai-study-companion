import { useEffect, useState } from 'react'
import { getProjectAnalytics } from '../../api/client'
import AnalyticsLayout, { ActivityList, Metric } from './AnalyticsLayout'

export default function ProjectDashboard({ threadId }) {
  const [data, setData] = useState(null); const [error, setError] = useState('')
  const load = async () => { if (!threadId) return; try { setError(''); setData(await getProjectAnalytics(threadId)) } catch (err) { setError(err.message) } }
  useEffect(() => { void load() }, [threadId])
  if (!threadId) return <AnalyticsLayout title="Project Analytics" subtitle="Select a project in the sidebar to see its analytics." loading={false} error="" onRefresh={() => {}} />
  return <AnalyticsLayout title="Project Analytics" subtitle={data?.project?.title || 'Learning and material health for this project.'} loading={!data && !error} error={error} onRefresh={load}>{data && <><div className="mt-6 grid gap-4 sm:grid-cols-3"><Metric label="Documents" value={data.documents} /><Metric label="Assessments" value={data.assessment_average == null ? '—' : `${data.assessment_average}%`} /><Metric label="Ingestion jobs" value={data.ingestion?.length} /></div><ActivityList items={data.activity} /></>}</AnalyticsLayout>
}
