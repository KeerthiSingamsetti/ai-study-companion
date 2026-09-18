import { motion } from 'framer-motion'
import { useWorkspace } from '../../context/WorkspaceContext'
import { WORKSPACE_GROUPS, visibleWorkspaces } from '../../config/toolRegistry'

export default function WorkspaceSection() {
  const { activeWorkspace, setActiveWorkspace, userRole } = useWorkspace()
  const workspaces = visibleWorkspaces(userRole)

  return (
    <nav className="mb-4 space-y-4">
      {WORKSPACE_GROUPS.map((group) => {
        const items = workspaces.filter((workspace) => workspace.group === group)
        if (items.length === 0) return null

        return (
          <div key={group}>
            <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              {group}
            </p>
            <ul className="space-y-0.5">
              {items.map((workspace) => {
                const Icon = workspace.icon
                const isActive = activeWorkspace === workspace.id
                return (
                  <li key={workspace.id} className="relative">
                    <button
                      type="button"
                      onClick={() => setActiveWorkspace(workspace.id)}
                      title={workspace.description}
                      aria-current={isActive ? 'page' : undefined}
                      className={`group relative flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium transition-colors ${
                        isActive ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)] hover:bg-white/[0.04] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      {isActive && (
                        <motion.span
                          layoutId="activeWorkspacePill"
                          className="absolute inset-0 rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-soft)]"
                          transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                        />
                      )}
                      <span
                        className={`relative z-10 grid size-6 shrink-0 place-items-center rounded-lg border transition-colors ${
                          isActive
                            ? 'border-[var(--accent)]/40 bg-[var(--accent)]/15 text-[var(--accent)]'
                            : 'border-transparent bg-white/[0.02] text-[var(--text-muted)] group-hover:text-[var(--text-primary)]'
                        }`}
                      >
                        <Icon className="size-3.5" />
                      </span>
                      <span className="relative z-10 truncate">{workspace.label}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )
      })}
    </nav>
  )
}
