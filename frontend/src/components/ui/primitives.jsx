import { motion } from 'framer-motion'
import { ArrowDownRight, ArrowUpRight, Minus, Sparkles } from 'lucide-react'

/* ────────────────────────────────────────────────────────────────
   Shared UI primitives — every surface composes these so the whole
   product reads as one design system instead of ad-hoc panels.
   ──────────────────────────────────────────────────────────────── */

/** Brand mark + wordmark used in the sidebar, auth screen and admin bar. */
export function Logo({ size = 36, showWordmark = true, subtitle = 'Learning Workspace' }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className="grid shrink-0 place-items-center rounded-2xl border border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/25 via-[var(--accent)]/10 to-transparent text-[var(--accent)] shadow-[var(--glow-accent)]"
        style={{ width: size, height: size }}
      >
        <Sparkles className="size-1/2" strokeWidth={2.2} />
      </div>
      {showWordmark && (
        <div className="min-w-0">
          <p className="truncate font-display text-sm font-bold tracking-tight text-[var(--text-primary)]">
            Study Companion
          </p>
          <p className="truncate text-[11px] font-medium text-[var(--text-muted)]">{subtitle}</p>
        </div>
      )}
    </div>
  )
}

/** Frosted content panel with an optional title row and action slot. */
export function Panel({ title, subtitle, icon: Icon, action, children, className = '', padded = true }) {
  return (
    <section className={`glass-card edge-highlight rounded-[var(--radius-card)] ${padded ? 'p-5' : ''} ${className}`}>
      {(title || action) && (
        <header className={`flex items-start justify-between gap-4 ${padded ? '' : 'border-b border-[var(--border)] p-5'}`}>
          <div className="flex min-w-0 items-start gap-3">
            {Icon && (
              <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)]">
                <Icon className="size-4" />
              </span>
            )}
            <div className="min-w-0">
              <h2 className="truncate font-display text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
              {subtitle && <p className="mt-0.5 text-xs text-[var(--text-muted)]">{subtitle}</p>}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={title || action ? 'mt-4' : ''}>{children}</div>
    </section>
  )
}

/** Small uppercase label used above sections and metric rows. */
export function Eyebrow({ children, className = '' }) {
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)] ${className}`}>
      {children}
    </span>
  )
}

/** Metric tile with optional delta indicator and tone. */
export function StatCard({ label, value, hint, icon: Icon, tone = 'accent', delta }) {
  const toneStyles = {
    accent: 'text-[var(--accent)] border-[var(--accent)]/25 bg-[var(--accent-soft)]',
    success: 'text-[var(--success)] border-[var(--success)]/25 bg-[var(--success-soft)]',
    warning: 'text-[var(--warning)] border-[var(--warning)]/25 bg-[var(--warning-soft)]',
    danger: 'text-[var(--danger)] border-[var(--danger)]/25 bg-[var(--danger-soft)]',
    blue: 'text-[var(--accent-blue)] border-[var(--accent-blue)]/25 bg-[var(--accent-blue-soft)]',
    teal: 'text-[var(--accent-teal)] border-[var(--accent-teal)]/25 bg-[var(--accent-teal-soft)]',
  }[tone] ?? ''

  const DeltaIcon = delta == null ? null : delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus

  return (
    <div className="glass-card rounded-[var(--radius-card)] p-4 transition-colors">
      <div className="flex items-center justify-between gap-3">
        <Eyebrow>{label}</Eyebrow>
        {Icon && (
          <span className={`grid size-7 place-items-center rounded-lg border ${toneStyles}`}>
            <Icon className="size-3.5" />
          </span>
        )}
      </div>
      <p className="mt-3 font-display text-2xl font-bold tabular-nums tracking-tight text-[var(--text-primary)]">
        {value ?? '—'}
      </p>
      <div className="mt-1 flex items-center gap-2">
        {DeltaIcon && (
          <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${delta > 0 ? 'text-[var(--success)]' : delta < 0 ? 'text-[var(--danger)]' : 'text-[var(--text-muted)]'}`}>
            <DeltaIcon className="size-3" />
            {Math.abs(delta)}%
          </span>
        )}
        {hint && <p className="truncate text-xs text-[var(--text-muted)]">{hint}</p>}
      </div>
    </div>
  )
}

/** Concept mastery meter — the PRD's ███████░░░ 72% made real. */
export function MasteryBar({ concept, score = 0, attempts, tone, animate = true }) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)))
  const resolvedTone = tone ?? (clamped >= 75 ? 'success' : clamped >= 60 ? 'accent' : 'danger')
  const gradient = {
    success: 'from-emerald-400 to-teal-400',
    accent: 'from-[var(--accent)] to-amber-300',
    danger: 'from-rose-400 to-orange-400',
    blue: 'from-sky-400 to-blue-400',
  }[resolvedTone]

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate text-xs font-medium text-[var(--text-primary)]" title={concept}>
          {concept}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {attempts != null && (
            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
              {attempts} {attempts === 1 ? 'attempt' : 'attempts'}
            </span>
          )}
          <span className="font-mono-numbers text-xs font-bold text-[var(--text-primary)]">{clamped}%</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-3)]">
        <motion.div
          className={`h-full rounded-full bg-gradient-to-r ${gradient}`}
          initial={animate ? { width: 0 } : false}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

const GROWTH = {
  improving: { label: 'Improving', tone: 'text-[var(--success)] border-[var(--success)]/30 bg-[var(--success-soft)]', Icon: ArrowUpRight },
  stable: { label: 'Stable', tone: 'text-[var(--accent-blue)] border-[var(--accent-blue)]/30 bg-[var(--accent-blue-soft)]', Icon: Minus },
  needs_attention: { label: 'Needs attention', tone: 'text-[var(--danger)] border-[var(--danger)]/30 bg-[var(--danger-soft)]', Icon: ArrowDownRight },
}

/** Growth classification chip: improving / stable / needs attention. */
export function GrowthBadge({ classification = 'stable' }) {
  const meta = GROWTH[classification] ?? GROWTH.stable
  const { Icon } = meta
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${meta.tone}`}>
      <Icon className="size-3" />
      {meta.label}
    </span>
  )
}

/** Next-action card used on both dashboards ("what should I do next?"). */
export function RecommendationCard({ text, trigger, action, onAction }) {
  const triggerLabel = {
    repeated_mistake: 'Repeated mistakes detected',
    low_mastery: 'Low mastery concept',
    improving: 'Momentum building',
    stale: 'No recent activity',
  }[trigger] ?? 'Recommendation'

  return (
    <div className="rounded-2xl border border-[var(--accent)]/25 bg-gradient-to-br from-[var(--accent-soft)] via-transparent to-transparent p-4">
      <Eyebrow className="text-[var(--accent)]">{triggerLabel}</Eyebrow>
      <p className="mt-2 text-sm leading-relaxed text-[var(--text-primary)]">{text}</p>
      {onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-[var(--accent)]/40 bg-[var(--accent)] px-3 py-1.5 text-xs font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)]"
        >
          {action ?? 'Start now'}
        </button>
      )}
    </div>
  )
}

const JOB_STATES = {
  ready: { label: 'Ready', cls: 'border-[var(--success)]/30 bg-[var(--success-soft)] text-[var(--success)]' },
  processing: { label: 'Processing', cls: 'border-[var(--accent-blue)]/30 bg-[var(--accent-blue-soft)] text-[var(--accent-blue)]' },
  queued: { label: 'Queued', cls: 'border-[var(--warning)]/30 bg-[var(--warning-soft)] text-[var(--warning)]' },
  failed: { label: 'Failed', cls: 'border-[var(--danger)]/30 bg-[var(--danger-soft)] text-[var(--danger)]' },
}

/** Background ingestion job state chip (queued → processing → ready/failed). */
export function JobStatePill({ state = 'queued', className = '' }) {
  const meta = JOB_STATES[state] ?? JOB_STATES.queued
  const isBusy = state === 'processing' || state === 'queued'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${meta.cls} ${className}`}>
      {isBusy ? (
        <span className="size-1.5 animate-pulse rounded-full bg-current" />
      ) : (
        <span className="size-1.5 rounded-full bg-current" />
      )}
      {meta.label}
    </span>
  )
}

/** Consistent empty / zero-data state. */
export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface-1)]/50 px-6 py-10 text-center">
      {Icon && (
        <span className="grid size-11 place-items-center rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text-muted)]">
          <Icon className="size-5" />
        </span>
      )}
      <div>
        <p className="font-display text-sm font-semibold text-[var(--text-primary)]">{title}</p>
        {description && <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-[var(--text-muted)]">{description}</p>}
      </div>
      {action}
    </div>
  )
}

/** Page shell: header with icon, title, subtitle and right-hand actions. */
export function PageHeader({ icon: Icon, title, subtitle, actions, children }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--border)] pb-5">
      <div className="flex min-w-0 items-start gap-3.5">
        {Icon && (
          <span className="grid size-11 shrink-0 place-items-center rounded-2xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] text-[var(--accent)]">
            <Icon className="size-5" />
          </span>
        )}
        <div className="min-w-0">
          <h1 className="font-display text-xl font-bold tracking-tight text-[var(--text-primary)]">{title}</h1>
          {subtitle && <p className="mt-1 max-w-2xl text-sm text-[var(--text-secondary)]">{subtitle}</p>}
          {children}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

/** Minimal inline bar chart — no chart dependency needed. */
export function BarChart({ data = [], tone = 'accent' }) {
  const max = Math.max(1, ...data.map((d) => d.value))
  const barTone = tone === 'teal' ? 'from-teal-400/80 to-teal-400/30' : tone === 'blue' ? 'from-sky-400/80 to-sky-400/30' : 'from-[var(--accent)]/80 to-[var(--accent)]/25'
  if (data.length === 0) return null
  return (
    <ul className="space-y-3">
      {data.map((row) => (
        <li key={row.label} className="space-y-1">
          <div className="flex items-baseline justify-between gap-3 text-xs">
            <span className="capitalize text-[var(--text-secondary)]">{row.label}</span>
            <span className="font-mono-numbers font-semibold text-[var(--text-primary)]">{row.value}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-3)]">
            <motion.div
              className={`h-full rounded-full bg-gradient-to-r ${barTone}`}
              initial={{ width: 0 }}
              animate={{ width: `${(row.value / max) * 100}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Activity timeline row shared by dashboards. */
export function ActivityItem({ label, detail, timestamp, icon: Icon, tone = 'accent' }) {
  const toneCls = {
    accent: 'text-[var(--accent)] bg-[var(--accent-soft)] border-[var(--accent)]/20',
    success: 'text-[var(--success)] bg-[var(--success-soft)] border-[var(--success)]/20',
    warning: 'text-[var(--warning)] bg-[var(--warning-soft)] border-[var(--warning)]/20',
    blue: 'text-[var(--accent-blue)] bg-[var(--accent-blue-soft)] border-[var(--accent-blue)]/20',
    teal: 'text-[var(--accent-teal)] bg-[var(--accent-teal-soft)] border-[var(--accent-teal)]/20',
  }[tone]

  return (
    <li className="flex items-start gap-3 py-2.5">
      <span className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg border ${toneCls}`}>
        {Icon ? <Icon className="size-3.5" /> : <span className="size-1.5 rounded-full bg-current" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium capitalize text-[var(--text-primary)]">{label}</p>
        {detail && <p className="mt-0.5 truncate text-[11px] text-[var(--text-muted)]">{detail}</p>}
      </div>
      {timestamp && <time className="shrink-0 text-[11px] text-[var(--text-muted)]">{timestamp}</time>}
    </li>
  )
}

/** Loading skeleton block used while analytics fetch. */
export function LoadingBlock({ label = 'Loading…', rows = 3 }) {
  return (
    <div role="status" className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton h-16 w-full" />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  )
}
