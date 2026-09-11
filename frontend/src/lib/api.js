import { API_BASE_URL, ApiError, request } from '../api/client'

export { API_BASE_URL, ApiError, request }

/**
 * Send a chat message over SSE stream, yielding tool_result and message events.
 */
export async function sendChatMessageStream(message, threadId, { onToolResult, onMessage }) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      ...(threadId ? { thread_id: threadId } : {}),
      stream: true,
    }),
  })

  if (!response.ok) {
    const rawBody = await response.text()
    let payload = null
    try {
      payload = rawBody ? JSON.parse(rawBody) : null
    } catch {
      // The backend may return a plain-text 500 response.
    }
    if (import.meta.env.DEV) {
      console.error('[StudyMate] /chat request failed', {
        status: response.status,
        statusText: response.statusText,
        body: payload ?? rawBody,
      })
    }
    const detail = typeof payload?.detail === 'string' ? payload.detail : 'The request could not be completed.'
    throw new ApiError(detail, response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let currentEvent = null
  let isStreamDone = false

  try {
    while (!isStreamDone) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) {
          currentEvent = null
          continue
        }
        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.slice(6).trim()
          if (currentEvent === 'done') {
            isStreamDone = true
            break
          }
        } else if (trimmed.startsWith('data:')) {
          const rawData = trimmed.slice(5).trim()
          if (rawData === '[DONE]' || currentEvent === 'done') {
            isStreamDone = true
            break
          }
          try {
            const parsed = JSON.parse(rawData)
            if (currentEvent === 'tool_result' || parsed.type === 'tool_result') {
              onToolResult?.(parsed)
            } else if (currentEvent === 'message' || parsed.message !== undefined) {
              onMessage?.(parsed)
            }
          } catch {
            // ignore parsing error
          }
        }
      }
    }
  } finally {
    try {
      await reader.cancel()
    } catch {
      // Reader might already be closed
    }
  }
}
