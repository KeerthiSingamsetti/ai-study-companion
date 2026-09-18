import { request } from './api'

export function reportQuizResult(documentId, topic, results) {
  return request('/progress/quiz-result', { method: 'POST', body: JSON.stringify({ document_id: documentId, topic, results }) })
}

export function reportFlashcardResult(documentId, topic, cards) {
  return request('/progress/flashcard-result', { method: 'POST', body: JSON.stringify({ document_id: documentId, topic, cards }) })
}

export function getStudyProgress(projectId) {
  // Scope the read to the active Project so one Space's progress/memory never
  // appears in another. Omitting it falls back to the learner's own aggregate.
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
  return request(`/progress${query}`)
}

