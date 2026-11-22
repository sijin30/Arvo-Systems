import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api.js'
import { Button, ErrorBanner, Field, inputClass } from '../../components.jsx'
import { CUSTOMER_SEVERITY } from '../../format.js'

export default function PortalNew() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ subject: '', description: '', priority: 'medium' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const t = await api('/portal/tickets', { method: 'POST', body: form })
      navigate(`/tickets/${t.id}`)
    } catch (err) {
      setError(err.status === 422 ? 'Please fill in the subject and describe the problem.' : err)
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold tracking-tight">Report a problem</h1>
      <p className="mb-5 text-sm text-slate-500">
        Tell us what happened. An agent from the support team will pick it up and reply here.
      </p>
      <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <ErrorBanner error={error} />
        <Field label="Subject">
          <input className={inputClass} required maxLength={200} value={form.subject} onChange={update('subject')} placeholder="A short summary" />
        </Field>
        <Field label="What happened?">
          <textarea className={inputClass} rows={6} required maxLength={10000} value={form.description} onChange={update('description')} placeholder="What were you doing, and what did you expect to happen?" />
        </Field>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-slate-700">How much does this affect you?</legend>
          <div className="space-y-2">
            {CUSTOMER_SEVERITY.map(([value, label, hint]) => (
              <label key={value} className={`flex cursor-pointer gap-3 rounded-lg border p-3 ${form.priority === value ? 'border-indigo-500 bg-indigo-50/50' : 'border-slate-200'}`}>
                <input type="radio" name="priority" className="mt-1" checked={form.priority === value} onChange={() => setForm({ ...form, priority: value })} />
                <span>
                  <span className="block text-sm font-medium">{label}</span>
                  <span className="block text-xs text-slate-500">{hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={() => navigate(-1)}>Cancel</Button>
          <Button variant="primary" disabled={busy}>{busy ? 'Sending…' : 'Send to support'}</Button>
        </div>
      </form>
    </div>
  )
}
