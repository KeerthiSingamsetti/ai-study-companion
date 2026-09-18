import {
  Calendar,
  ChartNoAxesCombined,
  FileText,
  Globe2,
  HelpCircle,
  Layers,
  LayoutDashboard,
  MessageSquare,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'

/**
 * Workspace registry.
 *
 * `group` drives sidebar sectioning; `adminOnly` hides the Admin console from
 * student accounts (the API separately enforces the admin role).
 */
export const WORKSPACES = [
  {
    id: 'home-dashboard',
    label: 'Home',
    title: 'Home Dashboard',
    shortName: 'Home',
    icon: LayoutDashboard,
    group: 'Learn',
    description: 'Continue learning, progress and your next action',
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
    id: 'documents',
    label: 'Materials',
    title: 'Learning Materials',
    shortName: 'Materials',
    icon: FileText,
    group: 'Learn',
    description: 'Upload and process course PDFs',
  },
  {
    id: 'quiz',
    label: 'Practice Quiz',
    title: 'Adaptive Quiz',
    shortName: 'Quiz',
    icon: HelpCircle,
    group: 'Practise',
    description: 'Adaptive practice with mastery feedback',
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
  {
    id: 'admin',
    label: 'Admin Console',
    title: 'Admin Operations',
    shortName: 'Admin',
    icon: ShieldCheck,
    group: 'Operate',
    adminOnly: true,
    description: 'Users, jobs, AI usage and system health',
  },
]

export const WORKSPACE_TOOLS = WORKSPACES

/** Workspaces visible to the signed-in account. */
export function visibleWorkspaces(role) {
  return WORKSPACES.filter((workspace) => !workspace.adminOnly || role === 'admin')
}

/** Stable render order of sidebar groups. */
export const WORKSPACE_GROUPS = ['Learn', 'Practise', 'Grow', 'Operate']
