import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FolderKanban,
  GraduationCap,
  Layers,
  Loader2,
  LogOut,
  MessageSquare,
  Plus,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
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
import { Logo } from './ui/primitives'

/* ── Shared field styling ─────────────────────────────────── */
const fieldClass =
  'w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]/70 focus:bg-[var(--surface-3)]'
const primaryButtonClass =
  'inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-3 text-sm font-bold text-[#1A1405] shadow-[var(--glow-accent)] transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-50'

const LOOP_STEPS = [
  { icon: BookOpen, label: 'Add material' },
  { icon: MessageSquare, label: 'Learn with the Tutor' },
  { icon: Layers, label: 'Practice & assess' },
  { icon: TrendingUp, label: 'Track mastery' },
  { icon: Target, label: 'Get the next action' },
]

/** Branded left rail shown beside every unauthenticated screen. */
function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden border-r border-[var(--border)] bg-[var(--surface-1)]/60 p-10 lg:flex lg:flex-col lg:justify-between">
      <div className="pointer-events-none absolute -left-24 top-[-10%] size-[420px] rounded-full bg-[var(--accent)]/10 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-[-15%] size-[380px] rounded-full bg-[var(--accent-teal)]/10 blur-3xl" />

      <div className="relative">
        <Logo size={40} subtitle="Persistent learning workspace" />
      </div>

      <div className="relative space-y-8">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
            <Sparkles className="size-3" /> AI-Powered Learning & Growth
          </span>
          <h1 className="mt-5 font-display text-4xl font-bold leading-[1.1] tracking-tight text-[var(--text-primary)]">
            Learn. Practice.
            <br />
            <span className="bg-gradient-to-r from-[var(--accent)] to-amber-200 bg-clip-text text-transparent">Measure. Grow.</span>
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-[var(--text-secondary)]">
            A study partner that remembers your context, grounds every answer in your own course material,
            and always knows what you should do next.
          </p>
        </div>

        <ol className="space-y-3">
          {LOOP_STEPS.map((step, index) => (
            <motion.li
              key={step.label}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.08 * index, duration: 0.35 }}
              className="flex items-center gap-3"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)]">
                <step.icon className="size-4" />
              </span>
              <span className="text-sm text-[var(--text-secondary)]">{step.label}</span>
            </motion.li>
          ))}
        </ol>
      </div>

      <ul className="relative grid grid-cols-2 gap-3 text-xs text-[var(--text-muted)]">
        {['Grounded citations', 'Concept mastery', 'Adaptive assessment', 'Project isolation'].map((feature) => (
          <li key={feature} className="flex items-center gap-2">
            <CheckCircle2 className="size-3.5 text-[var(--success)]" />
            {feature}
          </li>
        ))}
      </ul>
    </aside>
  )
}

/** Sign in / create account card. */
function AuthScreen({ onAuthed }) {
  const [register, setRegister] = useState(false)
  const [asAdmin, setAsAdmin] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    try {
      const result = register
        ? await registerUser(
            form.get('email'),
            form.get('password'),
            form.get('name').trim(),
            asAdmin ? 'admin' : 'student',
          )
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
    <div className="mx-auto w-full max-w-sm">
      <div className="lg:hidden">
        <Logo size={38} />
      </div>

      <h2 className="mt-8 font-display text-2xl font-bold tracking-tight text-[var(--text-primary)] lg:mt-0">
        {register ? 'Create your workspace' : 'Welcome back'}
      </h2>
      <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
        {register
          ? 'Set up an account to start a learning journey.'
          : 'Sign in to continue where you left off.'}
      </p>

      <form onSubmit={submit} className="mt-7 space-y-4">
        {register && (
          <label className="block space-y-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Display name</span>
            <input className={fieldClass} name="name" required autoComplete="name" placeholder="Ada Lovelace" />
          </label>
        )}
        <label className="block space-y-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Email</span>
          <input className={fieldClass} name="email" type="email" required autoComplete="email" placeholder="you@example.com" />
        </label>
        <label className="block space-y-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Password</span>
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
          <button
            type="button"
            onClick={() => setAsAdmin((prev) => !prev)}
            aria-pressed={asAdmin}
            className={`flex w-full items-center gap-3 rounded-[var(--radius-control)] border px-3.5 py-3 text-left transition ${
              asAdmin
                ? 'border-[var(--accent)]/40 bg-[var(--accent-soft)]'
                : 'border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--border-strong)]'
            }`}
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-[var(--border)] bg-[var(--surface-3)] text-[var(--accent)]">
              <Shield className="size-4" />
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-semibold text-[var(--text-primary)]">Platform administrator</span>
              <span className="block text-[11px] text-[var(--text-muted)]">
                Prototype toggle — unlocks the Admin operations console.
              </span>
            </span>
          </button>
        )}

        {error && (
          <p role="alert" className="rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
            {error}
          </p>
        )}

        <button className={primaryButtonClass} disabled={busy}>
          {busy && <Loader2 className="size-4 animate-spin" />}
          {busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}
        </button>
      </form>

      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setRegister(!register)
          setError('')
          setAsAdmin(false)
        }}
        className="mt-5 w-full text-center text-xs font-medium text-[var(--accent)] transition hover:text-[var(--accent-strong)]"
      >
        {register ? 'Already have an account? Sign in' : 'New here? Create an account'}
      </button>
    </div>
  )
}

/** Space / Project picker card. */
function SelectionCard({ title, meta, icon: Icon, onClick, disabled }) {
  return (
    <motion.button
      type="button"
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.99 }}
      disabled={disabled}
      onClick={onClick}
      className="group flex w-full items-start gap-3.5 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)] p-4 text-left transition hover:border-[var(--accent)]/40 hover:bg-[var(--surface-2)] disabled:opacity-50"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)] transition group-hover:border-[var(--accent)]/40 group-hover:bg-[var(--accent-soft)]">
        <Icon className="size-4.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-display text-sm font-semibold text-[var(--text-primary)]">{title}</span>
        {meta && <span className="mt-0.5 block truncate text-xs text-[var(--text-muted)]">{meta}</span>}
      </span>
      <ArrowRight className="mt-2 size-4 shrink-0 text-[var(--text-muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--accent)]" />
    </motion.button>
  )
}

/** Space → Project selection flow with inline creation. */
function Selection({ space, onSpace, onProject, onBack, user }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

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

  async function create(event) {
    event.preventDefault()
    const name = new FormData(event.currentTarget).get('name').trim()
    if (!name) return
    setBusy(true)
    setError('')
    try {
      const item = space ? await createProject(name, space.id) : await createSpace(name)
      if (space) onProject(item)
      else onSpace(item)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const isSpaces = !space

  return (
    <div className="w-full max-w-2xl">
      <PageHeading
        icon={isSpaces ? GraduationCap : FolderKanban}
        title={isSpaces ? 'Your Spaces' : `${space.name} · Projects`}
        subtitle={
          isSpaces
            ? 'Organize your learning journeys — one Space per course, certification or subject area.'
            : 'Each project keeps its own materials, conversations, concepts and mastery.'
        }
        onBack={isSpaces ? null : onBack}
        userName={user?.display_name}
      />

      {error && (
        <div role="alert" className="mt-5 flex items-center justify-between gap-3 rounded-[var(--radius-control)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs text-[var(--danger)]">
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
            {[0, 1].map((index) => (
              <div key={index} className="skeleton h-[74px] w-full" />
            ))}
          </div>
        ) : items.length === 0 && !error ? (
          <div className="rounded-[var(--radius-card)] border border-dashed border-[var(--border)] bg-[var(--surface-1)]/50 px-6 py-10 text-center">
            <span className="mx-auto grid size-12 place-items-center rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)]">
              {isSpaces ? <GraduationCap className="size-5" /> : <FolderKanban className="size-5" />}
            </span>
            <p className="mt-3 font-display text-sm font-semibold text-[var(--text-primary)]">
              {isSpaces ? 'No Spaces yet' : 'No projects yet'}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-[var(--text-muted)]">
              {isSpaces
                ? 'Create your first Space below — for example “Machine Learning” or “AWS Certification”.'
                : 'Create a project below to upload material and start learning with the Tutor.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {items.map((item) => (
              <SelectionCard
                key={item.id}
                title={item.name || item.title}
                meta={isSpaces ? 'Open Space' : 'Open project workspace'}
                icon={isSpaces ? GraduationCap : FolderKanban}
                disabled={busy}
                onClick={() => (space ? onProject(item) : onSpace(item))}
              />
            ))}
          </div>
        )}
      </div>

      <form onSubmit={create} className="mt-6 flex gap-2">
        <input
          aria-label={isSpaces ? 'Space name' : 'Project title'}
          name="name"
          required
          maxLength={200}
          placeholder={isSpaces ? 'New Space name' : 'New project title'}
          className={fieldClass}
        />
        <button
          type="submit"
          disabled={busy}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius-control)] bg-[var(--accent)] px-4 py-2.5 text-sm font-bold text-[#1A1405] transition hover:bg-[var(--accent-strong)] disabled:opacity-50"
        >
          <Plus className="size-4" />
          {busy ? 'Creating…' : 'Create'}
        </button>
      </form>
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
          {subtitle && <p className="mt-1 max-w-xl text-sm text-[var(--text-secondary)]">{subtitle}</p>}
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

export default function WorkspaceGate({ children }) {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(getAuthToken()))
  const [space, setSpace] = useState(null)
  const [project, setProject] = useState(null)

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
  }

  const selectSpace = (nextSpace) => {
    setProject(null)
    setSpace(nextSpace)
  }
  const switchProject = () => setProject(null)
  const switchSpace = () => {
    setProject(null)
    setSpace(null)
  }

  if (user && space && project) {
    return children({ user, space, project, onProject: setProject, onSpace: selectSpace, switchProject, switchSpace, logout })
  }

  return (
    <main className="app-aurora grid min-h-screen lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <BrandPanel />

      <section className="relative flex flex-col px-6 py-8 sm:px-10">
        {user && (
          <div className="mb-8 flex items-center justify-end gap-3 text-xs text-[var(--text-secondary)]">
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-1)] px-3 py-1.5">
              {user.display_name}
              {user.role === 'admin' && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[var(--accent-soft)] px-1.5 py-0.5 text-[10px] font-bold uppercase text-[var(--accent)]">
                  <Shield className="size-2.5" /> Admin
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-3 py-1.5 font-semibold transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
            >
              <LogOut className="size-3.5" /> Sign out
            </button>
          </div>
        )}

        <div className="flex flex-1 items-center justify-center py-6">
          {checking ? (
            <p role="status" className="inline-flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <Loader2 className="size-4 animate-spin" /> Checking session…
            </p>
          ) : !user ? (
            <AuthScreen onAuthed={setUser} />
          ) : (
            <Selection
              key={space?.id || 'spaces'}
              space={space}
              user={user}
              onSpace={setSpace}
              onProject={setProject}
              onBack={switchSpace}
            />
          )}
        </div>
      </section>
    </main>
  )
}
