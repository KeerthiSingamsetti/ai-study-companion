import { useEffect, useState } from 'react'
import { clearAuthToken, createProject, createSpace, getAuthToken, getMe, getSpaces, getThreads, loginUser, registerUser, setAuthToken } from '../api/client'

const inputClass = 'w-full rounded-xl border border-white/20 bg-white/5 p-3 text-white'
const buttonClass = 'rounded-xl bg-violet-600 px-4 py-3 font-semibold text-white disabled:opacity-50'

function LoginScreen({ onAuthed }) {
  const [register, setRegister] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
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
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return <section className="mx-auto max-w-md space-y-5">
    <h1 className="text-2xl font-bold">{register ? 'Create your StudyMate account' : 'Sign in to StudyMate'}</h1>
    <form onSubmit={submit} className="space-y-4">
      {register && <label className="block">Display name<input className={inputClass} name="name" required autoComplete="name" /></label>}
      <label className="block">Email<input className={inputClass} name="email" type="email" required autoComplete="email" /></label>
      <label className="block">Password<input className={inputClass} name="password" type="password" required autoComplete={register ? 'new-password' : 'current-password'} /></label>
      {error && <p role="alert" className="text-red-300">{error}</p>}
      <button className={buttonClass} disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}</button>
    </form>
    <button disabled={busy} onClick={() => { setRegister(!register); setError('') }} className="text-violet-300">{register ? 'Already registered? Sign in' : 'New here? Create an account'}</button>
  </section>
}

function Selection({ space, onSpace, onProject, onBack }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let alive = true
    const load = space ? getThreads(space.id) : getSpaces()
    load.then((data) => { if (alive) setItems(data) })
      .catch((err) => { if (alive) setError(err.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
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
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return <section className="mx-auto max-w-2xl space-y-6">
    {space && <button onClick={onBack} className="text-violet-300">← All Spaces</button>}
    <h1 className="text-3xl font-bold">{space ? `${space.name} / Projects` : 'Your Spaces'}</h1>
    <p className="text-slate-300">{space ? 'Choose a project. Chat and study tools use its documents and conversation.' : 'Organize your projects into Spaces, such as courses or semesters.'}</p>
    {error && <div role="alert" className="text-red-300">{error} <button onClick={() => { setError(''); setLoading(true); setRetry(retry + 1) }}>Retry</button></div>}
    {loading ? <p role="status">Loading…</p> : <div className="grid gap-3 sm:grid-cols-2">
      {items.map((item) => <button key={item.id} disabled={busy} onClick={() => space ? onProject(item) : onSpace(item)} className="rounded-2xl border border-white/15 bg-white/5 p-5 text-left hover:border-violet-400">{item.name || item.title}</button>)}
      {!items.length && !error && <p>No {space ? 'projects' : 'Spaces'} yet. Create your first one below.</p>}
    </div>}
    <form onSubmit={create} className="flex gap-3">
      <input aria-label={space ? 'Project title' : 'Space name'} name="name" required maxLength={200} placeholder={space ? 'New project title' : 'New Space name'} className={inputClass} />
      <button className={buttonClass} disabled={busy}>{busy ? 'Creating…' : 'Create'}</button>
    </form>
  </section>
}


export default function WorkspaceGate({ children }) {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(getAuthToken()))
  const [space, setSpace] = useState(null)
  const [project, setProject] = useState(null)
  useEffect(() => {
    let alive = true
    const expire = () => { clearAuthToken(); setUser(null); setSpace(null); setProject(null) }
    window.addEventListener('studymate:unauthorized', expire)
    if (getAuthToken()) {
      getMe().then((data) => { if (alive) setUser(data) })
        .catch(() => { if (alive) expire() })
        .finally(() => { if (alive) setChecking(false) })
    }
    return () => { alive = false; window.removeEventListener('studymate:unauthorized', expire) }
  }, [])
  function logout() {
    clearAuthToken(); setUser(null); setSpace(null); setProject(null)
  }
  const selectSpace = (nextSpace) => { setProject(null); setSpace(nextSpace) }
  const switchProject = () => setProject(null)
  const switchSpace = () => { setProject(null); setSpace(null) }
  if (user && space && project) return children({ user, space, project, onProject: setProject, onSpace: selectSpace, switchProject, switchSpace, logout })
  return <main className="min-h-screen bg-[#09090F] p-6 text-slate-100 sm:p-12">
    {user && <div className="mb-8 flex justify-end gap-4"><span>{user.display_name}</span><button onClick={logout}>Sign out</button></div>}
    {checking ? <p role="status">Checking session…</p> : !user ? <LoginScreen onAuthed={setUser} /> : <Selection key={space?.id || 'spaces'} space={space} onSpace={setSpace} onProject={setProject} onBack={switchSpace} />}
  </main>
}
