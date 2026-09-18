import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  FolderKanban,
  GraduationCap,
  Loader2,
  LogOut,
  Palette,
  Plus,
} from 'lucide-react'
import {
  clearAuthToken,
  createProject,
  createSpace,
  getAuthToken,
  getMe,
  getSpaces,
  getThreads,
  loginUser,
  registerUser,
  setAuthToken,
} from '../api/client'
import LandingPage from './LandingPage'
import AdminConsole from './admin/AdminConsole'
import { Logo } from './ui/primitives'

/* ── Shared field styling ─────────────────────────────────── */
const fieldClass =
  'w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]/70 focus:bg-[var(--surface-3)]'
const labelClass = 'text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]'
const primaryButtonClass =
  'bg-gradient-cta inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-control)] px-4 py-3 text-sm font-bold text-[#16110A] shadow-[var(--glow-accent)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50'

/** Optional visual customization palette for a Space. */
const SPACE_ACCENTS = [
  { id: '#F5B54A', label: 'Gold' },
  { id: '#60A5FA', label: 'Sky' },
  { id: '#2DD4BF', label: 'Teal' },
  { id: '#A78BFA', label: 'Violet' },
  { id: '#FB7185', label: 'Rose' },
  { id: '#4ADE80', label: 'Green' },
]

/* ────────────────────────────────────────────────────────────────
   Authentication
   ──────────────────────────────────────────────────────────────── */

function AuthScreen({ onAuthed, initialMode = 'signin' }) {
  const [mode, setMode] = useState(initialMode)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const register = mode === 'register'

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    try {
      const result = register
        ? await registerUser(form.get('email'), form.get('password'), form.get('name').trim())
        : await loginUser(form.get('email'), form.get('password'))
      setAuthToken(result.access_token)
      onAuthed(result.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-md">
      <h2 className="font-display text-2xl font-bold tracking-tight text-[var(--text-primary)]">
        {register ? 'Create your workspace' : 'Welcome back'}
      </h2>
      <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
        {register
          ? 'One account, many Spaces — each with its own materials, mastery and history.'
          : 'Sign in to pick up exactly where you left off.'}
      </p>

      {/* Segmented control instead of a link that silently swaps the form. */}
      <div
        role="tablist"
        aria-label="Authentication mode"
        className="mt-6 grid grid-cols-2 gap-1 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-1)] p-1"
      >
        {[
          { id: 'signin', label: 'Sign in' },
          { id: 'register', label: 'Create account' },
        ].map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={mode === tab.id}
            onClick={() => {
              setMode(tab.id)
              setError('')
            }}
            className={`rounded-[10px] px-3 py-2 text-xs font-bold transition ${
              mode === tab.id
                ? 'bg-[var(--accent)] text-[#1A1405] shadow-[var(--glow-accent)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-6 space-y-4">
        {register && (
          <label className="block space-y-1.5">
            <span className={labelClass}>Display name</span>
            <input className={fieldClass} name="name" required autoComplete="name" placeholder="Ada Lovelace" />
          </label>
        )}
        <label className="block space-y-1.5">
          <span className={labelClass}>Email</span>
          <input className={fieldClass} name="email" type="email" required autoComplete="email" placeholder="you@example.com" />
        </label>
        <label className="block space-y-1.5">
          <span className={labelClass}>Password</span>
          <input
            className={fieldClass}
            name="password"
            type="password"
            required
            autoComplete={register ? 'new-password' : 'current-password'}
            placeholder="••••••••"
          />
        </label>

        {register && (
          <p className="rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-[11px] leading-relaxed text-[var(--text-muted)]">
            The first account created on this deployment becomes the platform administrator — later accounts are
            student workspaces, and promotions are handled by the operator directly in the database.
          </p>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]"
          >
            {error}
          </p>
        )}

        <button className={primaryButtonClass} disabled={busy}>
          {busy && <Loader2 className="size-4 animate-spin" />}
          {busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}
        </button>
      </form>

      <p className="mt-5 text-center text-[11px] leading-relaxed text-[var(--text-muted)]">
        Your material stays scoped to the Project you upload it to — Spaces and Projects are isolated per account.
      </p>
    </div>
  )
}

/** Standalone auth view: aurora canvas, brand rail, centred card. */
function AuthView({ initialMode, onBack, onAuthed }) {
  return (
    <main className="app-aurora flex min-h-screen flex-col">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-6">
        <Logo size={38} subtitle="Persistent learning workspace" />
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border border-[var(--border)] px-3.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft className="size-3.5" /> Back to home
        </button>
      </div>

      <div className="flex flex-1 items-center justify-center px-6 pb-16">
        <div className="glass-card edge-highlight w-full max-w-lg rounded-[var(--radius-card)] p-7 sm:p-9">
          <AuthScreen onAuthed={onAuthed} initialMode={initialMode} />
        </div>
      </div>
    </main>
  )
}

/* ────────────────────────────────────────────────────────────────
   Space / Project selection + creation
   ──────────────────────────────────────────────────────────────── */

function SelectionCard({ title, description, meta, icon: Icon, accent, onClick, disabled }) {
  return (
    <motion.button
      type="button"
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.99 }}
      disabled={disabled}
      onClick={onClick}
      className="group relative flex w-full items-start gap-3.5 overflow-hidden rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-4 text-left transition hover:border-[var(--accent)]/40 hover:bg-[var(--surface-2)] disabled:opacity-50"
    >
      {accent && (
        <span
          aria-hidden="true"
          className="absolute inset-y-0 left-0 w-1"
          style={{ background: `linear-gradient(180deg, ${accent}, transparent)` }}
        />
      )}
      <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)] transition group-hover:border-[var(--accent)]/40 group-hover:bg-[var(--accent-soft)]">
        <Icon className="size-4.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-display text-sm font-semibold text-[var(--text-primary)]">{title}</span>
        {description && (
          <span className="mt-1 block line-clamp-2 text-xs leading-relaxed text-[var(--text-secondary)]">{description}</span>
        )}
        {meta && <span className="mt-1.5 block truncate text-[11px] text-[var(--text-muted)]">{meta}</span>}
      </span>
      <ArrowRight className="mt-3 size-4 shrink-0 text-[var(--text-muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--accent)]" />
    </motion.button>
  )
}

function Selection({ space, onSpace, onProject, onBack, user }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  /* Creation form state — the PRD requires a description, and a Project also
     carries a learning goal. */
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [learningGoal, setLearningGoal] = useState('')
  const [accent, setAccent] = useState(SPACE_ACCENTS[0].id)

  const isSpaces = !space

  useEffect(() => {
    let alive = true
    setLoading(true)
    const load = space ? getThreads(space.id) : getSpaces()
    load
      .then((data) => {
        if (alive) {
          setItems(data)
          setError('')
        }
      })
      .catch((err) => {
        if (alive) setError(err.message)
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [space, retry])

  function resetForm() {
    setShowForm(false)
    setName('')
    setDescription('')
    setLearningGoal('')
    setAccent(SPACE_ACCENTS[0].id)
  }

  async function create(event) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    if (isSpaces && !description.trim()) {
      setError('A Space needs a short description so its dashboard has context.')
      return
    }
    setBusy(true)
    setError('')
    try {
      if (isSpaces) {
        const item = await createSpace(trimmed, { description: description.trim(), accent })
        resetForm()
        onSpace(item)
      } else {
        const item = await createProject(trimmed, space.id, {
          description: description.trim(),
          learningGoal: learningGoal.trim(),
        })
        resetForm()
        onProject(item)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="w-full max-w-3xl">
      <PageHeading
        icon={isSpaces ? GraduationCap : FolderKanban}
        title={isSpaces ? 'Your Spaces' : `${space.name} · Projects`}
        subtitle={
          isSpaces
            ? 'A Space is a subject area — a course, certification or topic you are studying. Each one gets its own dashboard.'
            : space.description || 'A Project is the core learning workspace: its own materials, concepts, mastery and history.'
        }
        onBack={isSpaces ? null : onBack}
        userName={user?.display_name}
      />

      {error && (
        <div
          role="alert"
          className="mt-5 flex items-center justify-between gap-3 rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setRetry(retry + 1)}
            className="shrink-0 rounded-lg border border-[var(--danger)]/30 px-2.5 py-1 font-semibold transition hover:bg-[var(--danger)]/15"
          >
            Retry
          </button>
        </div>
      )}

      <div className="mt-5">
        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {[0, 1, 2, 3].map((index) => (
              <div key={index} className="skeleton h-[102px] w-full" />
            ))}
          </div>
        ) : items.length === 0 && !error ? (
          <div className="rounded-[var(--radius-card)] border border-dashed border-[var(--border)] bg-[var(--surface-1)]/50 px-6 py-12 text-center">
            <span className="mx-auto grid size-12 place-items-center rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)]">
              {isSpaces ? <GraduationCap className="size-5" /> : <FolderKanban className="size-5" />}
            </span>
            <p className="mt-3 font-display text-sm font-semibold text-[var(--text-primary)]">
              {isSpaces ? 'No Spaces yet' : 'No projects yet'}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-[var(--text-muted)]">
              {isSpaces
                ? 'Create your first Space below — for example “Machine Learning” or “AWS Certification”.'
                : 'Create a project below, then upload the material you want to learn from.'}
            </p>
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent)] px-3.5 py-2 text-xs font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)]"
            >
              <Plus className="size-3.5" /> {isSpaces ? 'New Space' : 'New project'}
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {items.map((item) => (
              <SelectionCard
                key={item.id}
                title={item.name || item.title}
                description={item.description || (isSpaces ? null : item.learning_goal)}
                meta={isSpaces ? 'Open Space dashboard' : 'Open project workspace'}
                icon={isSpaces ? GraduationCap : FolderKanban}
                accent={isSpaces ? item.accent : null}
                disabled={busy}
                onClick={() => (space ? onProject(item) : onSpace(item))}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Creation ──────────────────────────────────────────────── */}
      <div className="mt-7 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)]/60 p-4">
        {!showForm ? (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 text-sm font-bold text-[var(--accent)] transition hover:text-[var(--accent-strong)]"
          >
            <Plus className="size-4" /> {isSpaces ? 'Create a new Space' : 'Create a new project'}
          </button>
        ) : (
          <form onSubmit={create} className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display text-sm font-bold text-[var(--text-primary)]">
                {isSpaces ? 'New Space' : 'New project'}
              </h3>
              <button
                type="button"
                onClick={resetForm}
                className="text-[11px] font-semibold text-[var(--text-muted)] transition hover:text-[var(--text-primary)]"
              >
                Cancel
              </button>
            </div>

            <label className="block space-y-1.5">
              <span className={labelClass}>{isSpaces ? 'Space name' : 'Project name'}</span>
              <input
                className={fieldClass}
                value={name}
                required
                maxLength={200}
                onChange={(event) => setName(event.target.value)}
                placeholder={isSpaces ? 'Machine Learning' : 'Neural networks — midterm prep'}
              />
            </label>

            <label className="block space-y-1.5">
              <span className={labelClass}>
                Description {isSpaces && <span className="text-[var(--accent)]">· required</span>}
              </span>
              <textarea
                className={`${fieldClass} min-h-[74px] resize-y leading-relaxed`}
                value={description}
                maxLength={2000}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={
                  isSpaces
                    ? 'What does this Space cover? Feeds its dashboard summary.'
                    : 'What does this project cover? Shown on its dashboard.'
                }
              />
            </label>

            {!isSpaces && (
              <label className="block space-y-1.5">
                <span className={labelClass}>Learning goal</span>
                <input
                  className={fieldClass}
                  value={learningGoal}
                  maxLength={2000}
                  onChange={(event) => setLearningGoal(event.target.value)}
                  placeholder="e.g. Pass the midterm with 80%+"
                />
                <span className="block text-[11px] text-[var(--text-muted)]">
                  Recommendations use this as context for what to practise next.
                </span>
              </label>
            )}

            {isSpaces && (
              <div className="space-y-2">
                <span className={`${labelClass} inline-flex items-center gap-1.5`}>
                  <Palette className="size-3" /> Accent (optional)
                </span>
                <div className="flex flex-wrap gap-2">
                  {SPACE_ACCENTS.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      aria-label={option.label}
                      aria-pressed={accent === option.id}
                      onClick={() => setAccent(option.id)}
                      className={`size-8 rounded-xl border-2 transition ${
                        accent === option.id ? 'scale-105 border-[var(--text-primary)]' : 'border-transparent'
                      }`}
                      style={{ background: option.id }}
                    />
                  ))}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-2.5 text-sm font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)] disabled:opacity-50"
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              {busy ? 'Creating…' : isSpaces ? 'Create Space' : 'Create project'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

function PageHeading({ icon: Icon, title, subtitle, onBack, userName }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex min-w-0 items-start gap-3.5">
        <span className="grid size-11 shrink-0 place-items-center rounded-2xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] text-[var(--accent)]">
          <Icon className="size-5" />
        </span>
        <div className="min-w-0">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="mb-1 inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] transition hover:text-[var(--accent)]"
            >
              <ArrowLeft className="size-3" /> All Spaces
            </button>
          )}
          <h1 className="font-display text-2xl font-bold tracking-tight text-[var(--text-primary)]">{title}</h1>
          {subtitle && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">{subtitle}</p>}
        </div>
      </div>
      {userName && (
        <span className="hidden shrink-0 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-3 py-1.5 text-xs text-[var(--text-secondary)] sm:inline-flex">
          {userName}
        </span>
      )}
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Gate — landing → auth → Space/Project selection → workspace
   ──────────────────────────────────────────────────────────────── */

export default function WorkspaceGate({ children }) {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(getAuthToken()))
  const [space, setSpace] = useState(null)
  const [project, setProject] = useState(null)
  const [view, setView] = useState('landing')
  const [authMode, setAuthMode] = useState('signin')

  useEffect(() => {
    let alive = true
    const expire = () => {
      clearAuthToken()
      setUser(null)
      setSpace(null)
      setProject(null)
    }
    window.addEventListener('studymate:unauthorized', expire)
    if (getAuthToken()) {
      getMe()
        .then((data) => {
          if (alive) setUser(data)
        })
        .catch(() => {
          if (alive) expire()
        })
        .finally(() => {
          if (alive) setChecking(false)
        })
    }
    return () => {
      alive = false
      window.removeEventListener('studymate:unauthorized', expire)
    }
  }, [])

  function logout() {
    clearAuthToken()
    setUser(null)
    setSpace(null)
    setProject(null)
    setView('landing')
  }

  const selectSpace = (nextSpace) => {
    setProject(null)
    setSpace(nextSpace)
  }
  const switchSpace = () => {
    setProject(null)
    setSpace(null)
  }

  const openAuth = (mode) => {
    setAuthMode(mode)
    setView('auth')
  }

  /* Deliberate product decision (ASSUMPTIONS.md): the admin role is platform
     oversight (PRD §16 — inspect/view/filter verbs only), so admins land
     directly in the dedicated Admin Console. They never see the student
     onboarding (Space/Project creation) or the student learning UI; if an
     admin wants their own learner experience, that is a separate student
     account. */
  if (user && user.role === 'admin') {
    return <AdminConsole user={user} logout={logout} />
  }

  if (user && space && project) {
    return children({
      user,
      space,
      project,
      onProject: setProject,
      onSpace: selectSpace,
      switchProject: () => setProject(null),
      switchSpace,
      logout,
    })
  }

  if (checking) {
    return (
      <main className="app-aurora grid min-h-screen place-items-center">
        <p role="status" className="inline-flex items-center gap-2 text-sm text-[var(--text-muted)]">
          <Loader2 className="size-4 animate-spin" /> Checking session…
        </p>
      </main>
    )
  }

  if (!user) {
    return view === 'auth' ? (
      <AuthView initialMode={authMode} onBack={() => setView('landing')} onAuthed={setUser} />
    ) : (
      <LandingPage onSignIn={() => openAuth('signin')} onGetStarted={() => openAuth('register')} />
    )
  }

  return (
    <main className="app-aurora flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-6">
        <Logo size={38} subtitle="Persistent learning workspace" />
        <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-3 py-1.5">
            {user.display_name}
          </span>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-3 py-1.5 font-semibold transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          >
            <LogOut className="size-3.5" /> Sign out
          </button>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 items-center justify-center px-6 pb-16">
        <Selection
          key={space?.id || 'spaces'}
          space={space}
          user={user}
          onSpace={setSpace}
          onProject={setProject}
          onBack={switchSpace}
        />
      </div>
    </main>
  )
}
