import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { Button, ErrorBanner, Field, inputClass } from '../components.jsx'

const PRIORITIES = [
  ['urgent', 'Urgent', 'Customer cannot work at all. Reply in 2 working hours, fix within 1 working day.'],
  ['medium', 'Medium', 'Reply in half a working day, fix in about 3 working days.'],
  ['low', 'Low', 'Question or small request. Reply in 1 working day, finish in about 5 working days.'],
]

export default function NewTicket() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const related = params.get('related')
  const [form, setForm] = useState({
    subject: '',
    description: '',
    priority: 'medium',
    customer_name: params.get('name') || '',
    customer_email: params.get('email') || '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = { ...form }
      if (related) body.related_ticket_id = Number(related)
      const ticket = await api('/tickets', { method: 'POST', body })
      navigate(`/tickets/${ticket.id}`)
    } catch (err) {
      setError(err.status === 422 ? 'Please check the form: every field is required and the email must be valid.' : err)
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold tracking-tight">New ticket</h1>
      <p className="mb-5 text-sm text-slate-500">
        Log a problem on behalf of a customer.
        {related && <span className="font-medium text-indigo-700"> This is a follow-up to an earlier ticket and will link back to it.</span>}
      </p>
      <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <ErrorBanner error={error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Customer name">
            <input className={inputClass} required maxLength={120} value={form.customer_name} onChange={update('customer_name')} />
          </Field>
          <Field label="Customer email">
            <input className={inputClass} type="email" required value={form.customer_email} onChange={update('customer_email')} />
          </Field>
        </div>
        <Field label="Subject">
          <input className={inputClass} required maxLength={200} value={form.subject} onChange={update('subject')} />
        </Field>
        <Field label="What happened?">
          <textarea className={inputClass} rows={5} required maxLength={10000} value={form.description} onChange={update('description')} />
        </Field>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-slate-700">How bad is it?</legend>
          <div className="space-y-2">
            {PRIORITIES.map(([value, label, hint]) => (
              <label
                key={value}
                className={`flex cursor-pointer gap-3 rounded-lg border p-3 ${form.priority === value ? 'border-indigo-500 bg-indigo-50/50' : 'border-slate-200'}`}
              >
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
          <Button variant="primary" disabled={busy}>{busy ? 'Creating…' : 'Create ticket'}</Button>
        </div>
      </form>
    </div>
  )
}
