import { MessageSquare, FileText, HelpCircle, Layers, TrendingUp, Calendar, LayoutDashboard, ChartNoAxesCombined, Globe2 } from 'lucide-react'

export const WORKSPACES = [
  {
    id: 'home-dashboard', label: 'Home', title: 'Home Dashboard', shortName: 'Home',
    icon: LayoutDashboard,
    description: 'Personal study overview',
  },
  {
    id: 'project-dashboard', label: 'Project Analytics', title: 'Project Analytics', shortName: 'Project',
    icon: ChartNoAxesCombined, description: 'Active project learning analytics',
  },
  {
    id: 'global-analytics', label: 'Global Analytics', title: 'Global Analytics', shortName: 'Global',
    icon: Globe2, description: 'Cross-project study trends',
  },
  {
    id: 'chat',
    label: 'Chat',
    title: 'Chat Assistant',
    shortName: 'Chat',
    icon: MessageSquare,
    description: 'AI Study Companion',
  },
  {
    id: 'documents',
    label: 'Documents',
    title: 'Course Documents',
    shortName: 'Document',
    icon: FileText,
    description: 'Course PDFs & Reference Materials',
  },
  {
    id: 'quiz',
    label: 'Quiz',
    title: 'Practice Quiz',
    shortName: 'Quiz',
    icon: HelpCircle,
    description: 'Interactive Practice Quizzes',
  },
  {
    id: 'flashcards',
    label: 'Flashcards',
    title: 'Flashcard Decks',
    shortName: 'Flashcard',
    icon: Layers,
    description: 'Spaced Repetition Decks',
  },
  {
    id: 'progress',
    label: 'Progress',
    title: 'Study Progress',
    shortName: 'Analytics',
    icon: TrendingUp,
    description: 'Overall Performance & Weak Topics',
  },
  {
    id: 'planner',
    label: 'Study Plan',
    title: 'Study Planner',
    shortName: 'Planner',
    icon: Calendar,
    description: 'Customized Study Schedules',
  },
]

export const WORKSPACE_TOOLS = WORKSPACES
