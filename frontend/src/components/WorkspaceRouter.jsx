import { motion } from 'framer-motion'
import { useWorkspace } from '../context/WorkspaceContext'
import ChatWindow from './ChatWindow'
import DocumentPanel from './DocumentPanel'
import QuizWorkspace from './workspace/QuizWorkspace'
import FlashcardsWorkspace from './workspace/FlashcardsWorkspace'
import ProgressWorkspace from './workspace/ProgressWorkspace'
import PlannerWorkspace from './workspace/PlannerWorkspace'
import WorkspaceErrorBoundary from './WorkspaceErrorBoundary'
import HomeDashboard from './workspace/HomeDashboard'
import ProjectDashboard from './workspace/ProjectDashboard'
import GlobalAnalytics from './workspace/GlobalAnalytics'
import AdminDashboard from './workspace/AdminDashboard'

export default function WorkspaceRouter({
  user,
  documents = [],
  loadDocuments,
  loadThreads,
  handleInvalidThread,
  handleThreadCreated,
  chatResetKey,
}) {
  const {
    activeWorkspace,
    setActiveWorkspace,
    activeThreadId,
    setActiveThreadId,
    quizData,
    quizPrefill,
    flashcardData,
    flashcardPrefill,
    planData,
    progressData,
    handleUsePlanTopic,
    setQuizData,
    setFlashcardData,
    setPlanData,
    setProgressData,
  } = useWorkspace()

  // Workspace Framer Motion Transition Variant
  const transitionVariants = {
    initial: { opacity: 0, y: 12, filter: 'blur(4px)' },
    animate: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.28, ease: 'easeOut' } },
    exit: { opacity: 0, y: -12, filter: 'blur(4px)', transition: { duration: 0.2, ease: 'easeIn' } },
  }

  /** Open a project by id and route to a workspace (dashboards → deep links). */
  const openProject = (projectId, workspace = 'chat') => {
    if (projectId && setActiveThreadId) setActiveThreadId(projectId)
    setActiveWorkspace(workspace)
  }

  return (
    <div className="app-aurora relative h-full w-full flex-1 overflow-hidden">
      <div className={activeWorkspace === 'home-dashboard' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <WorkspaceErrorBoundary activeTab="home-dashboard">
          <HomeDashboard user={user} onOpenProject={openProject} />
        </WorkspaceErrorBoundary>
      </div>

      <div className={activeWorkspace === 'project-dashboard' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <WorkspaceErrorBoundary activeTab="project-dashboard">
          <ProjectDashboard
            threadId={activeThreadId}
            onOpenWorkspace={setActiveWorkspace}
            onUseTopic={(target, topic) => handleUsePlanTopic(target, topic)}
          />
        </WorkspaceErrorBoundary>
      </div>

      <div className={activeWorkspace === 'global-analytics' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <WorkspaceErrorBoundary activeTab="global-analytics">
          <GlobalAnalytics />
        </WorkspaceErrorBoundary>
      </div>

      <div className={activeWorkspace === 'admin' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <WorkspaceErrorBoundary activeTab="admin">
          <AdminDashboard />
        </WorkspaceErrorBoundary>
      </div>

      {/* 1. Chat Workspace */}
      <div className={activeWorkspace === 'chat' ? 'flex h-full w-full flex-col' : 'hidden'}>
        <motion.div
          key="chat-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'chat' ? 'animate' : 'initial'}
          className="flex h-full w-full flex-col"
        >
          <WorkspaceErrorBoundary activeTab="chat">
            <ChatWindow
              onFlashcardsCreated={setFlashcardData}
              onPlanCreated={setPlanData}
              onInvalidThread={handleInvalidThread}
              onQuizCreated={setQuizData}
              onProgressResult={setProgressData}
              onOpenProgressTab={() => setActiveWorkspace('progress')}
              onQuizTopic={(topic) => handleUsePlanTopic('quiz', topic)}
              onResponse={loadThreads}
              onThreadCreated={handleThreadCreated}
              resetKey={chatResetKey}
              threadId={activeThreadId}
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>

      {/* 2. Materials Workspace */}
      <div className={activeWorkspace === 'documents' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <motion.div
          key="documents-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'documents' ? 'animate' : 'initial'}
          className="mx-auto w-full max-w-4xl p-6"
        >
          <WorkspaceErrorBoundary activeTab="documents">
            <DocumentPanel
              documents={documents}
              onDocumentUploaded={loadDocuments}
              threadId={activeThreadId}
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>

      {/* 3. Quiz Workspace */}
      <div className={activeWorkspace === 'quiz' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <motion.div
          key="quiz-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'quiz' ? 'animate' : 'initial'}
          className="h-full w-full"
        >
          <WorkspaceErrorBoundary activeTab="quiz">
            <QuizWorkspace
              documents={documents}
              quizData={quizData}
              quizPrefill={quizPrefill}
              threadId={activeThreadId}
              onQuizUpdate={setQuizData}
              onDocumentUploaded={loadDocuments}
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>

      {/* 4. Flashcards Workspace */}
      <div className={activeWorkspace === 'flashcards' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <motion.div
          key="flashcards-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'flashcards' ? 'animate' : 'initial'}
          className="h-full w-full"
        >
          <WorkspaceErrorBoundary activeTab="flashcards">
            <FlashcardsWorkspace
              documents={documents}
              flashcardData={flashcardData}
              flashcardPrefill={flashcardPrefill}
              onFlashcardsUpdate={(updated) => setFlashcardData((prev) => (prev ? { ...prev, ...updated } : updated))}
              threadId={activeThreadId}
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>

      {/* 5. Progress Workspace */}
      <div className={activeWorkspace === 'progress' ? 'flex h-full w-full flex-col overflow-y-auto' : 'hidden'}>
        <motion.div
          key="progress-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'progress' ? 'animate' : 'initial'}
          className="h-full w-full"
        >
          <WorkspaceErrorBoundary activeTab="progress">
            <ProgressWorkspace
              progressData={progressData}
              onUseTopic={handleUsePlanTopic}
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>

      {/* 6. Study Plan Workspace */}
      <div className={activeWorkspace === 'planner' ? 'flex h-full w-full flex-col overflow-y-auto p-4' : 'hidden'}>
        <motion.div
          key="planner-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'planner' ? 'animate' : 'initial'}
          className="h-full w-full"
        >
          <WorkspaceErrorBoundary activeTab="planner">
            <PlannerWorkspace
              documents={documents}
              planData={planData}
              onPlanUpdate={setPlanData}
              onUseTopic={handleUsePlanTopic}
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>
    </div>
  )
}
