import { useRef, useState } from 'react'
import { uploadDocuments } from '../../api/client'

/**
 * Inline PDF upload for the Quiz zero-documents warning. Lets the user
 * upload into the current project without leaving the Quiz tab; the parent
 * refreshes its documents list afterwards, which removes the warning.
 */
export default function QuizEmptyUpload({ threadId, onUploaded }) {
  const inputRef = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  async function upload(fileList) {
    const files = Array.from(fileList || [])
    if (!threadId || files.length === 0) return
    setBusy(true)
    setError('')
    try {
      await uploadDocuments(threadId, files)
      onUploaded?.()
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        void upload(event.dataTransfer.files)
      }}
      className={`rounded-xl border border-dashed p-3 text-center transition ${
        dragging ? 'border-violet-400 bg-violet-500/10' : 'border-amber-400/40 bg-black/20'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="hidden"
        onChange={(event) => {
          void upload(event.target.files)
          event.target.value = ''
        }}
      />
      <p className="text-xs font-semibold text-amber-200">Upload a PDF into this project to quiz from it</p>
      <button
        type="button"
        disabled={busy || !threadId}
        onClick={() => inputRef.current?.click()}
        className="mt-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-violet-600/25 transition hover:brightness-110 disabled:opacity-50"
      >
        {busy ? 'Uploading…' : 'Choose PDF'}
      </button>
      {error && <p className="mt-2 text-xs text-red-300">{error}</p>}
    </div>
  )
}
