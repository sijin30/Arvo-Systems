import { useState } from 'react'
import { useAuth } from '../auth.jsx'
import { Button, ErrorBanner, Field, inputClass } from '../components.jsx'

const DEMO_STAFF = [
  ['Meera Nair', 'meera@arvosystems.example', 'Support lead'],
  ['Arjun Menon', 'arjun@arvosystems.example', 'Agent'],
  ['Anjali Krishnan', 'anjali@arvosystems.example', 'Agent'],
]

const friendly = (err) => {
  if (err.status === 422) return 'Please fill in every field. Passwords need at least 8 characters.'
  return err
}

export default function Login() {
  const { loginAgent, loginCustomer, signupCustomer } = useAuth()
  const [who, setWho] = useState('customer') // 'customer' | 'staff'
  const [mode, setMode] = useState('signin') // customers only: 'signin' | 'signup'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const signingUp = who === 'customer' && mode === 'signup'

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (who === 'staff') await loginAgent(email, password)
      else if (mode === 'signup') await signupCustomer(name, email, password)
      else await loginCustomer(email, password)
    } catch (err) {
      setError(friendly(err))
      setBusy(false)
    }
  }

  function switchWho(next) {
    setWho(next)
    setMode('signin')
    setError(null)
  }

  return (
    <div className="grid min-h-screen place-items-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-xl bg-indigo-600 text-xl font-semibold text-white">F</div>
          <h1 className="text-2xl font-semibold tracking-tight">Frontdesk</h1>
          <p className="mt-1 text-sm text-slate-500">Arvo Systems support desk</p>
        </div>

        <div role="tablist" className="mb-3 grid grid-cols-2 rounded-xl bg-slate-200/70 p-1 text-sm font-medium">
          {[
            ['customer', "I'm a customer"],
            ['staff', 'Support staff'],
          ].map(([key, label]) => (
            <button
              key={key}
              role="tab"
              aria-selected={who === key}
              onClick={() => switchWho(key)}
              className={`rounded-lg px-3 py-2 ${who === key ? 'bg-white shadow-sm' : 'text-slate-600'}`}
            >
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <h2 className="text-lg font-semibold">
            {who === 'staff' ? 'Staff sign in' : signingUp ? 'Create your account' : 'Customer sign in'}
          </h2>
          <ErrorBanner error={error} />
          {signingUp && (
            <Field label="Your name">
              <input className={inputClass} required maxLength={120} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
          )}
          <Field label="Email">
            <input className={inputClass} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password" hint={signingUp ? 'At least 8 characters.' : undefined}>
            <input
              className={inputClass}
              type="password"
              autoComplete={signingUp ? 'new-password' : 'current-password'}
              required
              minLength={signingUp ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button variant="primary" className="w-full" disabled={busy}>
            {busy ? 'Please wait…' : who === 'staff' ? 'Sign in' : signingUp ? 'Create account' : 'Sign in'}
          </Button>
          {who === 'customer' && (
            <p className="text-center text-sm text-slate-600">
              {signingUp ? 'Already have an account?' : 'New here?'}{' '}
              <button type="button" className="font-medium text-indigo-600 hover:underline" onClick={() => { setMode(signingUp ? 'signin' : 'signup'); setError(null) }}>
                {signingUp ? 'Sign in' : 'Create an account'}
              </button>
            </p>
          )}
        </form>

        {who === 'staff' ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white/60 p-4 text-sm text-slate-600">
            <p className="font-medium text-slate-700">Demo staff accounts</p>
            <p className="mt-1 text-xs">The password is in the README. Tap an account to fill in its email.</p>
            <ul className="mt-2 space-y-1">
              {DEMO_STAFF.map(([n, mail, role]) => (
                <li key={mail}>
                  <button type="button" onClick={() => setEmail(mail)} className="text-left text-indigo-700 hover:underline">
                    {n} <span className="text-slate-500">· {role} · {mail}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="mt-4 space-y-2 text-center text-xs text-slate-500">
            <p>Create a free account to report a problem to Arvo support and follow it until it is solved.</p>
            <p>
              Just looking around?{' '}
              <button type="button" onClick={() => { setMode('signin'); setEmail('priya@brightfin.example') }} className="text-indigo-700 hover:underline">
                Use the demo customer (priya@brightfin.example)
              </button>
              . The password is in the README.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
