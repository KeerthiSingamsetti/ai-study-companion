import { Component } from 'react'

/**
 * Keeps a workspace rendering failure isolated from the chat and thread UI.
 */
export default class WorkspaceErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidUpdate(previousProps) {
    if (previousProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error, errorInfo) {
    if (import.meta.env.DEV) {
      console.error('[StudyMate] workspace render failed:', error, errorInfo)
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          <p className="font-semibold">Something went wrong showing this workspace.</p>
          <p className="mt-1 text-xs text-rose-200/80">
            Your chat and conversations are still available. Select another tool tab to continue.
          </p>
        </div>
      )
    }

    return this.props.children
  }
}
