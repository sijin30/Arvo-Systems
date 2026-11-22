import { useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Button, ErrorBanner, Field, inputClass } from '../components.jsx'

export default function Account() {
  const { user, kind } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setDone(false)
    try {
      await api(kind === 'agent' ? '/auth/password' : '/portal/password', {
        method: 'POST',
        body: { current_password: current, new_password: next },
      })
      setCurrent('')
      setNext('')
      setDone(true)
    } catch (err) {
      setError(err.status === 422 ? 'Please fill in both fields.' : err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-1 text-xl font-semibold tracking-tight">Your account</h1>
      <p className="mb-5 text-sm text-slate-500">{user.name} · {user.email}</p>
      <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <h2 className="text-sm font-semibold">Change password</h2>
        <ErrorBanner error={error} />
        {done && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Your password has been changed.</p>}
        <Field label="Current password">
          <input className={inputClass} type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password" hint="At least 8 characters.">
          <input className={inputClass} type="password" autoComplete="new-password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        <Button variant="primary" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</Button>
      </form>
    </div>
  )
}
