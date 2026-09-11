import React from 'react'

/**
 * Signature pill-shaped "index tab" component anchored to top edges of content cards.
 * Inspired by catalog cards and physical study index tabs.
 */
export default function IndexTab({
  children,
  variant = 'accent', // 'accent' | 'success' | 'warning' | 'danger' | 'muted'
  className = '',
  icon: Icon = null,
}) {
  const variantStyles = {
    accent: 'bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent)]/30',
    success: 'bg-[var(--success-soft)] text-[var(--success)] border-[var(--success)]/30',
    warning: 'bg-[var(--warning-soft)] text-[var(--warning)] border-[var(--warning)]/30',
    danger: 'bg-[var(--danger-soft)] text-[var(--danger)] border-[var(--danger)]/30',
    muted: 'bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--border)]',
  }

  const selectedVariant = variantStyles[variant] || variantStyles.accent

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide uppercase font-sans ${selectedVariant} ${className}`}
    >
      {Icon && <Icon className="size-3 shrink-0" />}
      <span className="truncate">{children}</span>
    </span>
  )
}
