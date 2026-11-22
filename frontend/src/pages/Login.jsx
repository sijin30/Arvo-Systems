import { useState } from 'react'
import { useAuth } from '../auth.jsx'
import { Button, ErrorBanner, Field, inputClass } from '../components.jsx'

const DEMO = [
  ['Meera Nair', 'meera@arvosystems.example', 'Support lead'],
  ['Arjun Menon', 'arjun@arvosystems.example', 'Agent'],
  ['Anjali Krishnan', 'anjali@arvosystems.example', 'Agent'],
]

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-xl bg-indigo-600 text-xl font-semibold text-white">F</div>
          <h1 className="text-2xl font-semibold tracking-tight">Frontdesk</h1>
          <p className="mt-1 text-sm text-slate-500">Arvo Systems support desk</p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <ErrorBanner error={error} />
          <Field label="Email">
            <input className={inputClass} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password">
            <input className={inputClass} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Button variant="primary" className="w-full" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white/60 p-4 text-sm text-slate-600">
          <p className="font-medium text-slate-700">Demo accounts</p>
          <p className="mt-1 text-xs">
            Password for every account is in the README. Tap an account to fill in its email.
          </p>
          <ul className="mt-2 space-y-1">
            {DEMO.map(([name, mail, role]) => (
              <li key={mail}>
                <button type="button" onClick={() => setEmail(mail)} className="text-left text-indigo-700 hover:underline">
                  {name} <span className="text-slate-500">· {role} · {mail}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
