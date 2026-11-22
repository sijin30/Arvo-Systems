import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Badge, Button, ErrorBanner, Field, Spinner, inputClass } from '../components.jsx'

// A readable starting password the lead can hand over; the agent changes it after signing in.
function generatePassword() {
  const alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
  const bytes = crypto.getRandomValues(new Uint32Array(12))
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}

const empty = { name: '', email: '', role: 'agent', password: '' }

export default function Team() {
  const { agent: me } = useAuth()
  const [agents, setAgents] = useState(null)
  const [form, setForm] = useState({ ...empty, password: generatePassword() })
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null) // { email, password } shown once after creating
  const [resetFor, setResetFor] = useState(null) // agent id being reset
  const [resetPw, setResetPw] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const load = useCallback(() => api('/admin/agents').then(setAgents).catch(setError), [])
  useEffect(() => {
    load()
  }, [load])

  async function add(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/admin/agents', { method: 'POST', body: form })
      setCreated({ email: form.email.trim().toLowerCase(), password: form.password })
      setForm({ ...empty, password: generatePassword() })
      load()
    } catch (err) {
      setError(err.status === 422 ? 'Please fill in the name and email.' : err)
    } finally {
      setBusy(false)
    }
  }

  async function toggle(a) {
    setError(null)
    try {
      await api(`/admin/agents/${a.id}/${a.is_active ? 'deactivate' : 'activate'}`, { method: 'POST' })
      load()
    } catch (err) {
      setError(err)
    }
  }

  async function reset(a) {
    setError(null)
    try {
      await api(`/admin/agents/${a.id}/password`, { method: 'POST', body: { password: resetPw } })
      setCreated({ email: a.email, password: resetPw, reset: true })
      setResetFor(null)
      setResetPw('')
    } catch (err) {
      setError(err)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Support team</h1>
        <p className="text-sm text-slate-500">Create accounts for new agents, switch accounts off when someone leaves, and reset forgotten passwords.</p>
      </div>
      <ErrorBanner error={error} onClose={() => setError(null)} />

      {created && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <p className="font-medium">{created.reset ? 'Password reset.' : 'Agent created.'} Share these details securely. The password is not shown again.</p>
          <p className="mt-1 font-mono">{created.email} / {created.password}</p>
          <button className="mt-2 text-emerald-800 underline" onClick={() => setCreated(null)}>Done</button>
        </div>
      )}

      <form onSubmit={add} className="grid gap-4 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 md:grid-cols-5">
        <div className="md:col-span-1"><Field label="Name"><input className={inputClass} required maxLength={120} value={form.name} onChange={update('name')} /></Field></div>
        <div className="md:col-span-1"><Field label="Email"><input className={inputClass} type="email" required value={form.email} onChange={update('email')} /></Field></div>
        <div className="md:col-span-1">
          <Field label="Role">
            <select className={inputClass} value={form.role} onChange={update('role')}>
              <option value="agent">Agent</option>
              <option value="lead">Lead</option>
            </select>
          </Field>
        </div>
        <div className="md:col-span-1">
          <Field label="Starting password">
            <input className={`${inputClass} font-mono`} required minLength={8} value={form.password} onChange={update('password')} />
          </Field>
        </div>
        <div className="flex items-end"><Button variant="primary" className="w-full" disabled={busy}>{busy ? 'Adding…' : 'Add agent'}</Button></div>
      </form>

      {!agents ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Active tickets</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {agents.map((a) => (
                <tr key={a.id} className={a.is_active ? '' : 'bg-slate-50 text-slate-500'}>
                  <td className="px-4 py-3 font-medium">{a.name}</td>
                  <td className="px-4 py-3">{a.email}</td>
                  <td className="px-4 py-3">{a.role === 'lead' ? <Badge tone="indigo">Lead</Badge> : 'Agent'}</td>
                  <td className="px-4 py-3">{a.is_active ? <Badge tone="green">Active</Badge> : <Badge>Switched off</Badge>}</td>
                  <td className="px-4 py-3 tabular-nums">{a.active_tickets}</td>
                  <td className="px-4 py-3 text-right">
                    {resetFor === a.id ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="w-40"><input className={`${inputClass} font-mono`} placeholder="New password" minLength={8} value={resetPw} onChange={(e) => setResetPw(e.target.value)} /></span>
                        <Button variant="primary" disabled={resetPw.length < 8} onClick={() => reset(a)}>Save</Button>
                        <Button onClick={() => { setResetFor(null); setResetPw('') }}>Cancel</Button>
                      </span>
                    ) : (
                      <span className="inline-flex gap-3">
                        <button className="text-indigo-600 hover:underline" onClick={() => { setResetFor(a.id); setResetPw(generatePassword()) }}>Reset password</button>
                        {a.id !== me.id && (
                          <button className={a.is_active ? 'text-red-600 hover:underline' : 'text-emerald-700 hover:underline'} onClick={() => toggle(a)}>
                            {a.is_active ? 'Switch off' : 'Switch on'}
                          </button>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-slate-500">
        An agent who still owns active tickets cannot be switched off until the tickets are reassigned. There must always be one active lead.
      </p>
    </div>
  )
}
