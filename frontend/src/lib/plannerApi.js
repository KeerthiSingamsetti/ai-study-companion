import { request } from './api'
export function generateStudyPlan(documentId, topics, numDays, examDate) {
  return request('/planner/generate', { method: 'POST', body: JSON.stringify({ document_id: documentId, topics: topics?.length ? topics : null, num_days: numDays, exam_date: examDate || null }) })
}
