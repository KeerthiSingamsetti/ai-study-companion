import { request } from './api'

/**
 * Generate / regenerate flashcards directly via the backend endpoint.
 *
 * @param {string} documentId - ID of the target document
 * @param {string} topic - Topic for the flashcards
 * @param {number} [numCards=10] - Number of cards requested
 * @returns {Promise<import('../schemas/flashcard').FlashcardGenerateResponse>} The generated flashcards payload
 */
export async function generateFlashcards(documentId, topic, numCards = 10) {
  return request('/flashcards/generate', {
    method: 'POST',
    body: JSON.stringify({
      document_id: documentId,
      topic,
      num_cards: numCards,
    }),
  })
}
