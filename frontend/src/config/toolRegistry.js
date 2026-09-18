import {
  Boxes,
  Calendar,
  ChartNoAxesCombined,
  FileText,
  Globe2,
  HelpCircle,
  Layers,
  LayoutDashboard,
  MessageSquare,
  SquarePen,
  TrendingUp,
} from 'lucide-react'

/**
 * Workspace registry.
 *
 * Ordering is deliberate: it follows the learning loop a student actually walks
 * (`Materials → Tutor → Quiz → Assessment → Growth → Analytics`) rather than an
 * arbitrary feature list, so the sidebar reads as a guided path.
 *
 * `group` drives sidebar sectioning. The registry is student-only by design:
 * admin-role accounts are routed to the dedicated Admin Console in the gate and
 * never mount this sidebar at all (see ASSUMPTIONS.md, admin interface decision).
 */
export const WORKSPACES = [
  {
    id: 'home-dashboard',
    label: 'Home',
    title: 'Home Dashboard',
    shortName: 'Home',
    icon: LayoutDashboard,
    group: 'Overview',
    description: 'Continue learning, progress and your next action',
  },
  {
    id: 'space-dashboard',
    label: 'Space Overview',
    title: 'Space Dashboard',
    shortName: 'Space',
    icon: Boxes,
    group: 'Overview',
    description: 'Projects, activity, progress and areas needing attention',
  },
  {
    id: 'documents',
    label: 'Materials',
    title: 'Learning Materials',
    shortName: 'Materials',
    icon: FileText,
    group: 'Learn',
    description: 'Upload and process course PDFs',
  },
  {
    id: 'chat',
    label: 'AI Tutor',
    title: 'AI Tutor',
    shortName: 'Tutor',
    icon: MessageSquare,
    group: 'Learn',
    description: 'Grounded answers with citations from your material',
  },
  {
    id: 'quiz',
    label: 'Adaptive Quiz',
    title: 'Adaptive Quiz',
    shortName: 'Quiz',
    icon: HelpCircle,
    group: 'Practise',
    description: 'Adaptive multiple-choice practice with mastery feedback',
  },
  {
    id: 'assessment',
    label: 'Open-ended Assessment',
    title: 'Open-ended Assessment',
    shortName: 'Assess',
    icon: SquarePen,
    group: 'Practise',
    description: 'Explain concepts in your own words and get graded feedback',
  },
  {
    id: 'flashcards',
    label: 'Flashcards',
    title: 'Flashcard Decks',
    shortName: 'Flashcards',
    icon: Layers,
    group: 'Practise',
    description: 'Recall practice from your own material',
  },
  {
    id: 'planner',
    label: 'Study Plan',
    title: 'Study Planner',
    shortName: 'Planner',
    icon: Calendar,
    group: 'Practise',
    description: 'Day-by-day revision schedules',
  },
  {
    id: 'progress',
    label: 'Progress',
    title: 'Study Progress',
    shortName: 'Progress',
    icon: TrendingUp,
    group: 'Grow',
    description: 'Weak topics, attempts and focus areas',
  },
  {
    id: 'project-dashboard',
    label: 'Project Analytics',
    title: 'Project Analytics',
    shortName: 'Project',
    icon: ChartNoAxesCombined,
    group: 'Grow',
    description: 'Mastery, growth and next step for this project',
  },
  {
    id: 'global-analytics',
    label: 'Global Analytics',
    title: 'Global Analytics',
    shortName: 'Global',
    icon: Globe2,
    group: 'Grow',
    description: 'Cross-project trends and AI usage',
  },
]

export const WORKSPACE_TOOLS = WORKSPACES

/** Workspaces visible to the signed-in account. Admins never reach this
 * registry at all — the gate routes them to the dedicated Admin Console —
 * so every entry here is a student learning surface. */
export function visibleWorkspaces() {
  return WORKSPACES
}

/** Stable render order of sidebar groups. */
export const WORKSPACE_GROUPS = ['Overview', 'Learn', 'Practise', 'Grow', 'Operate']
