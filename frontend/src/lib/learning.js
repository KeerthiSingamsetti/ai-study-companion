import {
  Activity,
  AlertTriangle,
  Award,
  BookOpen,
  CheckCircle2,
  GraduationCap,
  Lightbulb,
  ListChecks,
  MessageSquare,
  RefreshCw,
  Sparkles,
  SquarePen,
  TrendingUp,
  Upload,
} from 'lucide-react'

/**
 * Presentation helpers for learning-loop data.
 *
 * `EVENT_META` keys mirror the backend's event taxonomy
 * (`app/db/crud.py::EVENT_TYPES`), so the activity feed never has to guess.
 *
 * Growth classification is authoritative when the API returns it: the backend
 * classifies each concept from its real mastery timeline (improving / stable /
 * needs_attention, see `app/services/learning.py`). `classifyScore` is only the
 * fallback for surfaces that have a score but no history.
 */

/** Map persisted event types onto human labels, icons and tones. */
export const EVENT_META = {
  project_created: { label: 'Project created', icon: Sparkles, tone: 'accent' },
  material_uploaded: { label: 'Material uploaded', icon: Upload, tone: 'blue' },
  material_processing_started: { label: 'Processing started', icon: RefreshCw, tone: 'warning' },
  material_processing_completed: { label: 'Material ready', icon: CheckCircle2, tone: 'success' },
  material_processing_failed: { label: 'Processing failed', icon: AlertTriangle, tone: 'danger' },
  tutor_interaction: { label: 'Tutor interaction', icon: MessageSquare, tone: 'accent' },
  quiz_attempted: { label: 'Quiz attempted', icon: ListChecks, tone: 'warning' },
  question_answered: { label: 'Question answered', icon: ListChecks, tone: 'blue' },
  assessment_completed: { label: 'Assessment graded', icon: GraduationCap, tone: 'success' },
  mastery_updated: { label: 'Mastery updated', icon: TrendingUp, tone: 'blue' },
  recommendations_generated: { label: 'Next step recommended', icon: Lightbulb, tone: 'accent' },
  project_activity: { label: 'Project activity', icon: Activity, tone: 'accent' },
}

export function describeEvent(type = '') {
  const meta = EVENT_META[type]
  if (meta) return meta
  return {
    label: String(type).replaceAll('_', ' '),
    icon: Activity,
    tone: 'accent',
  }
}

/** Score → growth classification using the policy's low-mastery band. */
export function classifyScore(score) {
  if (score == null) return 'stable'
  if (score < 60) return 'needs_attention'
  if (score >= 75) return 'improving'
  return 'stable'
}

/**
 * Prefer the backend's real growth classification (computed from the concept's
 * mastery timeline) and fall back to the score band only when absent.
 */
export function growthOf(row) {
  return row?.classification ?? classifyScore(row?.score)
}

/** Signed delta formatted for display, e.g. "+4.2" or "−3.0". */
export function formatDelta(delta) {
  if (typeof delta !== 'number' || Number.isNaN(delta)) return null
  if (Math.abs(delta) < 0.05) return 'no change'
  return `${delta > 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)}`
}

/** Human band label for a mastery score. */
export function masteryBand(score) {
  if (score == null) return { label: 'No evidence', tone: 'muted' }
  if (score >= 75) return { label: 'Strong', tone: 'success' }
  if (score >= 60) return { label: 'On track', tone: 'accent' }
  if (score >= 45) return { label: 'Developing', tone: 'warning' }
  return { label: 'Needs attention', tone: 'danger' }
}

/**
 * The one-tap self-report scale. Mirrors CONFIDENCE_SCALE in
 * backend/app/services/calibration.py — the levels must stay in step with the
 * backend, which is the side that does the arithmetic.
 */
export const CONFIDENCE_OPTIONS = [
  { level: 1, label: 'Guess', score: 20 },
  { level: 2, label: 'Not sure', score: 40 },
  { level: 3, label: 'Fairly sure', score: 60 },
  { level: 4, label: 'Confident', score: 80 },
  { level: 5, label: 'Certain', score: 100 },
]

const CALIBRATION_META = {
  overconfident: {
    label: 'Overconfident',
    cls: 'border-[var(--danger)]/30 bg-[var(--danger-soft)] text-[var(--danger)]',
    accent: 'var(--danger)',
  },
  underconfident: {
    label: 'Underconfident',
    cls: 'border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
    accent: 'var(--accent-blue)',
  },
  well_calibrated: {
    label: 'Well calibrated',
    cls: 'border-[var(--success)]/30 bg-[var(--success-soft)] text-[var(--success)]',
    accent: 'var(--success)',
  },
  insufficient_evidence: {
    label: 'Not enough evidence',
    cls: 'border-[var(--border)] text-[var(--text-muted)]',
    accent: 'var(--text-muted)',
  },
}

/** Badge styling for a calibration direction reported by the backend. */
export function calibrationMeta(direction) {
  return CALIBRATION_META[direction] ?? CALIBRATION_META.insufficient_evidence
}

/** Compact relative timestamp for activity feeds. */
export function relativeTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date)
}

/** Mean of numeric values, or null when there is no evidence. */
export function average(values = []) {
  const numeric = values.filter((value) => typeof value === 'number' && !Number.isNaN(value))
  if (numeric.length === 0) return null
  return Math.round(numeric.reduce((sum, value) => sum + value, 0) / numeric.length)
}

/** Weakest-first ordering for mastery rows. */
export function rankMastery(rows = []) {
  return [...rows].sort((a, b) => (a?.score ?? 101) - (b?.score ?? 101))
}

/**
 * The PRD's guided path — Materials → Tutor → Quiz → Growth → Analytics.
 * Each step maps to a real workspace id so the dashboard can deep-link into it.
 */
export const STUDY_FLOW = [
  { id: 'documents', label: 'Materials', description: 'Upload the source material', icon: BookOpen },
  { id: 'chat', label: 'Tutor', description: 'Ask grounded questions', icon: MessageSquare },
  { id: 'quiz', label: 'Quiz', description: 'Adaptive multiple choice', icon: ListChecks },
  { id: 'assessment', label: 'Assess', description: 'Explain it in your own words', icon: SquarePen },
  { id: 'project-dashboard', label: 'Growth', description: 'Mastery over time', icon: TrendingUp },
  { id: 'global-analytics', label: 'Analytics', description: 'Cross-project trends', icon: Award },
]

export const LEARNING_STEPS = STUDY_FLOW
