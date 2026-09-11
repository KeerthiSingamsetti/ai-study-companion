import { motion } from 'framer-motion'
import { useWorkspace } from '../context/WorkspaceContext'
import ChatWindow from './ChatWindow'
import DocumentPanel from './DocumentPanel'
import QuizWorkspace from './workspace/QuizWorkspace'
import FlashcardsWorkspace from './workspace/FlashcardsWorkspace'
import ProgressWorkspace from './workspace/ProgressWorkspace'
import PlannerWorkspace from './workspace/PlannerWorkspace'
import WorkspaceErrorBoundary from './WorkspaceErrorBoundary'

export default function WorkspaceRouter({
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

  return (
    <div className="relative flex-1 h-full w-full overflow-hidden bg-[#09090F]">
      {/* 1. Chat Workspace */}
      <div className={activeWorkspace === 'chat' ? 'flex flex-col h-full w-full' : 'hidden'}>
        <motion.div
          key="chat-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'chat' ? 'animate' : 'initial'}
          className="h-full w-full flex flex-col"
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

      {/* 2. Documents Workspace */}
      <div className={activeWorkspace === 'documents' ? 'flex flex-col h-full w-full p-4 overflow-y-auto' : 'hidden'}>
        <motion.div
          key="documents-panel"
          variants={transitionVariants}
          initial="initial"
          animate={activeWorkspace === 'documents' ? 'animate' : 'initial'}
          className="h-full w-full"
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
      <div className={activeWorkspace === 'quiz' ? 'flex flex-col h-full w-full overflow-y-auto' : 'hidden'}>
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
            />
          </WorkspaceErrorBoundary>
        </motion.div>
      </div>

      {/* 4. Flashcards Workspace */}
      <div className={activeWorkspace === 'flashcards' ? 'flex flex-col h-full w-full overflow-y-auto' : 'hidden'}>
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
      <div className={activeWorkspace === 'progress' ? 'flex flex-col h-full w-full overflow-y-auto' : 'hidden'}>
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
      <div className={activeWorkspace === 'planner' ? 'flex flex-col h-full w-full overflow-y-auto p-4' : 'hidden'}>
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
