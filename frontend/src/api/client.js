export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const TOKEN_KEY = 'studymate_token'

export const getAuthToken = () => localStorage.getItem(TOKEN_KEY)
export const setAuthToken = (token) => localStorage.setItem(TOKEN_KEY, token)
export const clearAuthToken = () => localStorage.removeItem(TOKEN_KEY)

// Shared by JSON requests, uploads, and the streaming chat client.
export async function authenticatedFetch(path, options = {}) {
  const token = getAuthToken()
  const headers = new Headers(options.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (response.status === 401 && token && getAuthToken() === token) {
    clearAuthToken()
    window.dispatchEvent(new Event('studymate:unauthorized'))
  }
  return response
}

export function loginUser(email, password) {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function registerUser(email, password, displayName) {
  // Role is decided server-side (first account = admin); never sent by the client.
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, display_name: displayName }),
  })
}

export const getMe = () => request('/auth/me')
export const getSpaces = () => request('/spaces')

/**
 * A Space requires a name and description, with optional visual customization.
 * `description` is what makes a Space dashboard meaningful, so it is sent (and
 * encouraged in the UI) alongside the name.
 */
export const createSpace = (name, { description, accent, icon } = {}) =>
  request('/spaces', {
    method: 'POST',
    body: JSON.stringify({ name, description: description || null, accent: accent || null, icon: icon || null }),
  })

export const updateSpace = (spaceId, patch) =>
  request(`/spaces/${encodeURIComponent(spaceId)}`, { method: 'PATCH', body: JSON.stringify(patch) })

/** A Project carries a name, description and learning goal. */
export const createProject = (title, spaceId, { description, learningGoal } = {}) =>
  request('/threads', {
    method: 'POST',
    body: JSON.stringify({
      title,
      space_id: spaceId,
      description: description || null,
      learning_goal: learningGoal || null,
    }),
  })

export const updateProject = (projectId, patch) =>
  request(`/threads/${encodeURIComponent(projectId)}`, { method: 'PATCH', body: JSON.stringify(patch) })


export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const response = await authenticatedFetch(path, {
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

export function getThreads(spaceId) {
  return request(spaceId ? `/threads?space_id=${encodeURIComponent(spaceId)}` : '/threads')
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

/** Background ingestion job states for a project (queued → processing → ready/failed). */
export function getIngestionJobs(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}/ingestion-jobs`)
}

/** Retry a failed ingestion job. */
export function retryIngestionJob(jobId) {
  return request(`/ingestion-jobs/${encodeURIComponent(jobId)}/retry`, { method: 'POST' })
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

export function getHomeAnalytics() {
  return request('/analytics/home')
}

export function getProjectAnalytics(threadId) {
  return request(`/analytics/projects/${encodeURIComponent(threadId)}`)
}

export function getGlobalAnalytics() {
  return request('/analytics/global')
}

/** Space-level dashboard: projects, activity, progress and attention areas. */
export function getSpaceAnalytics(spaceId) {
  return request(`/analytics/spaces/${encodeURIComponent(spaceId)}`)
}

/* ── Admin operations console (admin role required by the API) ──── */
export function getAdminOperations() {
  return request('/admin/operations')
}

export function getAdminProduct() {
  return request('/admin/product')
}

/* ── Dedicated admin console (admin role required by the API) ────── */
export function getAdminUsers(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString()
  return request(`/admin/users${qs ? `?${qs}` : ''}`)
}

export function getAdminSpaces() {
  return request('/admin/spaces')
}

export function getAdminProjects(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString()
  return request(`/admin/projects${qs ? `?${qs}` : ''}`)
}

export function getAdminAiUsage(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString()
  return request(`/admin/ai-usage${qs ? `?${qs}` : ''}`)
}

export function getAdminEvaluation() {
  return request('/admin/evaluation')
}

export function getAdminJobs(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString()
  return request(`/admin/jobs${qs ? `?${qs}` : ''}`)
}

export function getAdminHealth() {
  return request('/admin/health')
}

/** Per-user learning journey (admin only): projects, activity, assessments, AI usage. */
export function getAdminUser(userId) {
  return request(`/admin/users/${encodeURIComponent(userId)}`)
}

/** Platform-wide activity feed with query filters (admin only). */
export function getAdminActivity(filters = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value != null && value !== '') params.set(key, value)
  }
  const qs = params.toString()
  return request(`/admin/activity${qs ? `?${qs}` : ''}`)
}

/** Distinct event types for the activity filter dropdown (admin only). */
export function getAdminActivityTypes() {
  return request('/admin/activity/types')
}

/**
 * User / Project picker options for the activity feed (admin only).
 * Pass a userId to narrow the Project options to that account.
 */
export function getAdminActivityFilters(params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString()
  return request(`/admin/activity/filters${qs ? `?${qs}` : ''}`)
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
