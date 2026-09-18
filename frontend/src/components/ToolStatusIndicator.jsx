/**
 * Visual badge indicator for completed tool operations inside chat history.
 */
export function ToolStatusIndicator({ message, detail }) {
  if (!message) return null
  return (
    <div className="my-2.5 flex animate-fade-in items-center gap-2.5 rounded-xl border border-[var(--success)]/30 bg-[var(--success-soft)] px-3.5 py-2.5 text-xs text-[var(--success)]">
      <span className="relative flex size-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--success)] opacity-75" />
        <span className="relative inline-flex size-2 rounded-full bg-[var(--success)]" />
      </span>
      <span className="font-semibold">{message}</span>
      {detail && <span className="text-[var(--text-secondary)]">— {detail}</span>}
    </div>
  )
}

export default ToolStatusIndicator
