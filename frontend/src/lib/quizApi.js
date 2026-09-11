import { request } from './api'

/**
 * Regenerate a document quiz directly via backend endpoint.
 *
 * @param {string} documentId - ID of the target document
 * @param {string} topic - Topic for quiz questions
 * @param {number} [numQuestions=10] - Number of questions requested
 * @param {'easy'|'medium'|'hard'} [difficulty='medium'] - Desired difficulty level
 * @returns {Promise<import('../schemas/quiz').QuizGenerateResponse>} The generated quiz payload
 */
export async function regenerateQuiz(documentId, topic, numQuestions = 10, difficulty = 'medium') {
  return request('/quiz/generate', {
    method: 'POST',
    body: JSON.stringify({
      document_id: documentId,
      topic,
      num_questions: numQuestions,
      difficulty,
    }),
  })
}
