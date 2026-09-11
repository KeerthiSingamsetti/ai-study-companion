import { createContext, useCallback, useContext, useState } from 'react'

const WorkspaceContext = createContext(null)

export function WorkspaceProvider({ children, value = {} }) {
  const [activeWorkspace, setActiveWorkspace] = useState('chat')
  const [activeThreadIdInternal, setActiveThreadIdInternal] = useState(null)
  const [quizPrefill, setQuizPrefill] = useState(null)
  const [flashcardPrefill, setFlashcardPrefill] = useState(null)
  const [progressData, setProgressData] = useState(null)
  const [quizData, setQuizData] = useState(null)
  const [flashcardData, setFlashcardData] = useState(null)
  const [planData, setPlanData] = useState(null)

  const activeThreadId = value?.activeThreadId ?? activeThreadIdInternal
  const setActiveThreadId = value?.setActiveThreadId ?? setActiveThreadIdInternal

  const handleUsePlanTopic = useCallback((targetWorkspace, topic, docId, options = {}) => {
    const prefillPayload = {
      documentId: docId || options.documentId || '',
      documentName: options.documentName || '',
      topic: topic || '',
      difficulty: options.difficulty || 'medium',
      numQuestions: options.numQuestions || 10,
      quizMode: options.quizMode || 'topic',
      source: options.source || 'study-progress',
    }

    if (targetWorkspace === 'quiz') {
      setQuizData(null) // Clear active quiz data to ensure weak topic setup form is shown immediately
      setQuizPrefill(prefillPayload)
      setActiveWorkspace('quiz')
    } else if (targetWorkspace === 'flashcards') {
      setFlashcardData(null) // Clear active flashcard data
      setFlashcardPrefill({
        documentId: docId || options.documentId || '',
        topic: topic || '',
        numCards: 10,
      })
      setActiveWorkspace('flashcards')
    }
  }, [])

  const contextValue = {
    // Merge external value first so internal state is the primary authority
    ...(value || {}),
    activeWorkspace,
    setActiveWorkspace,
    activeThreadId,
    setActiveThreadId,
    quizPrefill,
    setQuizPrefill,
    flashcardPrefill,
    setFlashcardPrefill,
    progressData,
    setProgressData,
    quizData,
    setQuizData,
    flashcardData,
    setFlashcardData,
    planData,
    setPlanData,
    handleUsePlanTopic,
  }

  return (
    <WorkspaceContext.Provider value={contextValue}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider')
  }
  return context
}
