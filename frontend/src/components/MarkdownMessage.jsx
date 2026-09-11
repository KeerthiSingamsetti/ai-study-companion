import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Returns visual styling rules per section title/heading.
 */
function getSectionStyle(titleText = '') {
  const text = titleText.toLowerCase()

  if (text.includes('overview') || text.includes('definition')) {
    return {
      border: 'border-l-violet-500 border-violet-500/30',
      bg: 'bg-gradient-to-r from-violet-950/40 via-slate-900/60 to-purple-950/20',
      accent: 'text-violet-300',
      icon: '📖',
    }
  }
  if (text.includes('intuition')) {
    return {
      border: 'border-l-amber-500 border-amber-500/30',
      bg: 'bg-gradient-to-r from-amber-950/30 via-slate-900/60 to-yellow-950/20',
      accent: 'text-amber-300',
      icon: '💡',
    }
  }
  if (text.includes('how it works') || text.includes('working') || text.includes('steps')) {
    return {
      border: 'border-l-sky-500 border-sky-500/30',
      bg: 'bg-gradient-to-r from-sky-950/30 via-slate-900/60 to-blue-950/20',
      accent: 'text-sky-300',
      icon: '⚙️',
    }
  }
  if (text.includes('formula') || text.includes('diagram') || text.includes('math')) {
    return {
      border: 'border-l-emerald-500 border-emerald-500/30',
      bg: 'bg-gradient-to-r from-emerald-950/30 via-slate-900/60 to-teal-950/20',
      accent: 'text-emerald-300',
      icon: '🧮',
    }
  }
  if (text.includes('example')) {
    return {
      border: 'border-l-emerald-400 border-emerald-500/30',
      bg: 'bg-gradient-to-r from-emerald-950/30 via-slate-900/60 to-green-950/20',
      accent: 'text-emerald-300',
      icon: '✅',
    }
  }
  if (text.includes('key points') || text.includes('key takeaways') || text.includes('takeaways')) {
    return {
      border: 'border-l-indigo-500 border-indigo-500/30',
      bg: 'bg-gradient-to-r from-indigo-950/30 via-slate-900/60 to-violet-950/20',
      accent: 'text-indigo-300',
      icon: '⭐',
    }
  }
  if (text.includes('advantages') || text.includes('limitations') || text.includes('tradeoff')) {
    return {
      border: 'border-l-rose-500 border-rose-500/30',
      bg: 'bg-gradient-to-r from-rose-950/30 via-slate-900/60 to-orange-950/20',
      accent: 'text-rose-300',
      icon: '⚠️',
    }
  }

  // Default section style
  return {
    border: 'border-l-slate-500 border-slate-700/50',
    bg: 'bg-slate-900/70',
    accent: 'text-slate-200',
    icon: '📍',
  }
}

/**
 * Rich markdown component for rendering structured AI study responses.
 * Renders sections in card-like containers with section icons & colored borders.
 * Gracefully handles live streaming markdown tokens without error flashing.
 */
export default function MarkdownMessage({ content }) {
  if (!content) return null

  return (
    <div className="space-y-3 text-slate-200 text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // H1: Document / Concept Title Header
          h1({ children }) {
            return (
              <div className="mb-4 pb-2 border-b border-slate-800">
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  <span className="inline-block size-2.5 rounded-full bg-violet-400 animate-pulse" />
                  {children}
                </h1>
              </div>
            )
          },

          // H2 & H3: Section Cards with Icons and Left-Borders
          h2({ children }) {
            const titleStr = React.Children.toArray(children).join('')
            const style = getSectionStyle(titleStr)
            return (
              <div className={`my-3.5 overflow-hidden rounded-xl border border-l-4 ${style.border} ${style.bg} p-4 shadow-sm transition-all`}>
                <h2 className={`text-base font-semibold tracking-wide ${style.accent} flex items-center gap-2 mb-2`}>
                  <span>{style.icon}</span>
                  <span>{children}</span>
                </h2>
              </div>
            )
          },

          h3({ children }) {
            const titleStr = React.Children.toArray(children).join('')
            const style = getSectionStyle(titleStr)
            return (
              <div className={`my-3 rounded-lg border border-l-4 ${style.border} ${style.bg} p-3`}>
                <h3 className={`text-sm font-semibold ${style.accent} flex items-center gap-2 mb-1.5`}>
                  <span>{style.icon}</span>
                  <span>{children}</span>
                </h3>
              </div>
            )
          },

          // Paragraphs
          p({ children }) {
            return <p className="text-sm leading-relaxed text-slate-300 my-2">{children}</p>
          },

          // Bold Text
          strong({ children }) {
            return <strong className="font-semibold text-white">{children}</strong>
          },

          // Lists
          ul({ children }) {
            return <ul className="my-2 space-y-1.5 pl-4 text-sm text-slate-200 list-disc">{children}</ul>
          },
          ol({ children }) {
            return <ol className="my-2 space-y-1.5 pl-4 text-sm text-slate-200 list-decimal">{children}</ol>
          },
          li({ children }) {
            return <li className="leading-relaxed text-slate-200">{children}</li>
          },

          // Tables
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-1">
                <table className="w-full text-left text-xs text-slate-300 border-collapse">{children}</table>
              </div>
            )
          },
          thead({ children }) {
            return <thead className="bg-slate-900/90 text-violet-300 border-b border-slate-800">{children}</thead>
          },
          th({ children }) {
            return <th className="px-3.5 py-2.5 font-semibold text-slate-200">{children}</th>
          },
          td({ children }) {
            return <td className="px-3.5 py-2.5 border-t border-slate-800/60 text-slate-300">{children}</td>
          },

          // Code blocks & inline code
          code({ inline, className, children, ...props }) {
            if (inline) {
              return (
                <code className="rounded bg-slate-950/80 px-1.5 py-0.5 font-mono text-xs text-emerald-300 ring-1 ring-inset ring-slate-800" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <pre className="my-2.5 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/90 p-3 font-mono text-xs leading-5 text-emerald-300">
                <code className={className} {...props}>{children}</code>
              </pre>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
