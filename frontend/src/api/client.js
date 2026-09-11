export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  })

  if (response.status === 204) {
    return null
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    let detail = 'The request could not be completed.'
    if (typeof payload?.detail === 'string') {
      detail = payload.detail
    } else if (Array.isArray(payload?.detail)) {
      detail = payload.detail.map((err) => err.msg || JSON.stringify(err)).join(', ')
    } else if (payload?.detail && typeof payload.detail === 'object') {
      detail = JSON.stringify(payload.detail)
    } else if (typeof payload?.message === 'string') {
      detail = payload.message
    }
    throw new ApiError(detail, response.status)
  }

  return payload
}

export function getThreads() {
  return request('/threads')
}

export function getThreadMessages(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}/messages`)
}

export function renameThread(threadId, title) {
  return request(`/threads/${encodeURIComponent(threadId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export function removeThread(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}`, { method: 'DELETE' })
}

export function sendChatMessage(message, threadId) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, ...(threadId ? { thread_id: threadId } : {}) }),
  })
}

export function getDocuments(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}/documents`)
}

export function uploadDocuments(threadId, files) {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  return request(`/threads/${encodeURIComponent(threadId)}/documents/upload`, {
    method: 'POST',
    body: formData,
  })
}

export function removeDocument(documentId) {
  return request(`/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' })
}

export function getStudyLog(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}/study-log`)
}

/**
 * Query an existing FAISS index for debug purposes.
 * payload shape must match RagQueryRequest:
 *   { query, index_path, k?, use_reranking?, use_hybrid_search?, rerank_top_k? }
 */
export function queryRag(payload) {
  return request('/rag/query', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
