import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { motion } from 'framer-motion'
import { WORKSPACES } from '../../config/toolRegistry'
import { useWorkspace } from '../../context/WorkspaceContext'

export default function WorkspaceSection() {
  const [isOpen, setIsOpen] = useState(true)
  const { activeWorkspace, setActiveWorkspace } = useWorkspace()

  return (
    <div className="mb-4">
      {/* Section Header */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
      >
        <span>Workspaces</span>
        <ChevronDown
          className={`size-3.5 transition-transform duration-200 ${
            isOpen ? 'rotate-0' : '-rotate-90'
          }`}
        />
      </button>

      {/* Collapsible Content */}
      <div
        className={`grid transition-all duration-300 ease-in-out ${
          isOpen ? 'grid-rows-[1fr] opacity-100 mt-1' : 'grid-rows-[0fr] opacity-0'
        }`}
      >
        <div className="overflow-hidden">
          <ul className="space-y-1">
            {WORKSPACES.map((workspace) => {
              const Icon = workspace.icon
              const isActive = activeWorkspace === workspace.id
              return (
                <li key={workspace.id} className="relative">
                  <button
                    type="button"
                    onClick={() => setActiveWorkspace(workspace.id)}
                    className={`group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-xs font-semibold transition-all ${
                      isActive
                        ? 'text-white'
                        : 'text-[var(--text-secondary)] hover:bg-white/[0.04] hover:text-white'
                    }`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="activeWorkspacePill"
                        className="absolute inset-0 rounded-xl bg-gradient-to-r from-violet-600/20 to-indigo-600/10 border border-violet-500/30 shadow-md shadow-violet-500/10"
                        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                      />
                    )}

                    <div className={`relative z-10 grid size-6 place-items-center rounded-lg border transition-all ${
                      isActive
                        ? 'border-violet-500/40 bg-violet-500/20 text-violet-300 shadow-sm'
                        : 'border-white/5 bg-white/[0.02] text-[var(--text-muted)] group-hover:border-white/10 group-hover:text-white group-hover:scale-105'
                    }`}>
                      <Icon className="size-3.5" />
                    </div>

                    <span className="relative z-10 truncate">{workspace.label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
