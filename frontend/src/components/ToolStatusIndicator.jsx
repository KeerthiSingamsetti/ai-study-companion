/**
 * Visual badge indicator for completed tool operations inside chat history.
 */
export function ToolStatusIndicator({ message, detail }) {
  if (!message) return null
  return (

    <div className="my-2.5 flex items-center gap-2.5 rounded-xl border border-emerald-500/30 bg-emerald-950/40 px-3.5 py-2.5 text-xs text-emerald-300 shadow-md backdrop-blur animate-fade-in">
      <span className="relative flex size-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
      </span>
      <span className="font-semibold text-emerald-200">{message}</span>
      {detail && <span className="text-slate-400">— {detail}</span>}
    </div>
  )
}

export default ToolStatusIndicator
