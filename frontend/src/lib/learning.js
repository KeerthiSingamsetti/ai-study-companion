import {
  Activity,
  Award,
  BookOpen,
  Brain,
  CheckCircle2,
  FileText,
  GraduationCap,
  Layers,
  Lightbulb,
  ListChecks,
  MessageSquare,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  Upload,
} from 'lucide-react'

/**
 * Presentation helpers for learning-loop data.
 *
 * Growth classification is a UI heuristic over the same thresholds the
 * backend mastery policy uses (see ASSUMPTIONS.md): mastery below the
 * 60-point band is reported as "needs attention" because the concept is
 * scoring below the policy's low-mastery trigger. Improving/stable require
 * score history, which dashboards derive from attempt counts where the API
 * does not expose deltas — the label is never presented as a measurement.
 */

/** Map persisted event types onto human labels, icons and tones. */
export const EVENT_META = {
  project_created: { label: 'Project created', icon: Sparkles, tone: 'accent' },
  material_uploaded: { label: 'Material uploaded', icon: Upload, tone: 'blue' },
  material_processing_started: { label: 'Processing started', icon: RefreshCw, tone: 'warning' },
  material_processing_completed: { label: 'Material ready', icon: CheckCircle2, tone: 'success' },
  material_processing_failed: { label: 'Processing failed', icon: FileText, tone: 'danger' },
  tutor_turn: { label: 'Tutor interaction', icon: MessageSquare, tone: 'accent' },
  tutor_message: { label: 'Tutor interaction', icon: MessageSquare, tone: 'accent' },
  quiz_attempt: { label: 'Quiz attempt', icon: ListChecks, tone: 'warning' },
  quiz_completed: { label: 'Quiz completed', icon: ListChecks, tone: 'success' },
  assessment_completed: { label: 'Assessment graded', icon: GraduationCap, tone: 'success' },
  mastery_updated: { label: 'Mastery updated', icon: TrendingUp, tone: 'blue' },
  recommendation_created: { label: 'Recommendation', icon: Lightbulb, tone: 'accent' },
  flashcard_review: { label: 'Flashcard review', icon: Layers, tone: 'teal' },
  document_indexed: { label: 'Indexed for retrieval', icon: BookOpen, tone: 'blue' },
  concept_extracted: { label: 'Concept extracted', icon: Brain, tone: 'teal' },
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

/** Human band label for a mastery score. */
export function masteryBand(score) {
  if (score == null) return { label: 'No evidence', tone: 'muted' }
  if (score >= 75) return { label: 'Strong', tone: 'success' }
  if (score >= 60) return { label: 'On track', tone: 'accent' }
  if (score >= 45) return { label: 'Developing', tone: 'warning' }
  return { label: 'Needs attention', tone: 'danger' }
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

export const LEARNING_STEPS = [
  { id: 'materials', label: 'Materials', icon: BookOpen },
  { id: 'tutor', label: 'Tutor', icon: MessageSquare },
  { id: 'quiz', label: 'Practice', icon: ListChecks },
  { id: 'mastery', label: 'Mastery', icon: Award },
  { id: 'growth', label: 'Growth', icon: TrendingUp },
  { id: 'next', label: 'Next action', icon: Target },
]
