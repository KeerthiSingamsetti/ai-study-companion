import { request } from './api'

export function reportQuizResult(documentId, topic, results) {
  return request('/progress/quiz-result', { method: 'POST', body: JSON.stringify({ document_id: documentId, topic, results }) })
}

export function reportFlashcardResult(documentId, topic, cards) {
  return request('/progress/flashcard-result', { method: 'POST', body: JSON.stringify({ document_id: documentId, topic, cards }) })
}

export function getStudyProgress() {
  return request('/progress')
}

