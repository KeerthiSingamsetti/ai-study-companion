import { request } from './api'

/**
 * Learning-loop client.
 *
 * Mastery is an estimate that evolves with evidence, so every call here either
 * submits evidence (quiz answers, a graded explanation) or reads the current
 * estimate plus the next recommended action.
 */

/**
 * Ask the backend which concept to practise next, and at what difficulty.
 *
 * The decision is made by the mastery policy on the server (weakest mastery
 * plus repeated recent mistakes), not by the last answer, so the client never
 * picks the topic itself. Rejects with 409 before there is any evidence.
 */
export function getAdaptiveQuizTarget(projectId) {
  return request(`/learning/quiz/next?project_id=${encodeURIComponent(projectId)}`)
}

/** Submit adaptive quiz answers as concept-mastery evidence. */
export function reportQuizEvidence({ projectId, documentId, topic, concept, difficulty = 'medium', results }) {
  return request('/learning/quiz-result', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      document_id: documentId || null,
      topic,
      concept: concept || topic,
      difficulty,
      results,
    }),
  })
}

/** Generate grounded open-ended questions for a concept. */
export function generateAssessment({ projectId, concept, documentId, numQuestions = 1, difficulty = 'medium' }) {
  return request('/learning/assessment/generate', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      concept,
      document_id: documentId || null,
      num_questions: numQuestions,
      difficulty,
    }),
  })
}

/**
 * Grade one open-ended answer and receive the refreshed mastery estimate.
 * `predictedScore` is the learner's own pre-grading prediction (0-100);
 * supplying it is what makes the calibration comparison possible.
 */
export function gradeAssessment({
  projectId,
  concept,
  question,
  answer,
  referenceAnswer,
  rubric,
  documentId,
  difficulty = 'medium',
  predictedScore = null,
}) {
  return request('/learning/assessment/grade', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      concept,
      question,
      answer,
      reference_answer: referenceAnswer || '',
      rubric: rubric || undefined,
      document_id: documentId || null,
      difficulty,
      predicted_score: predictedScore,
    }),
  })
}

/** Graded history, per-concept growth and active recommendations for a project. */
export function getAssessmentSummary(projectId) {
  return request(`/learning/assessment/${encodeURIComponent(projectId)}`)
}

export function getRecommendations(projectId) {
  return request(`/learning/recommendations/${encodeURIComponent(projectId)}`)
}

export function dismissRecommendation(recommendationId) {
  return request(`/learning/recommendations/${encodeURIComponent(recommendationId)}/dismiss`, { method: 'POST' })
}
