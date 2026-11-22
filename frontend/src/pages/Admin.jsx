import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { Button, ErrorBanner, Field, Spinner, inputClass } from '../components.jsx'

const dayFmt = new Intl.DateTimeFormat('en-IN', { timeZone: 'UTC', weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })

export default function Admin() {
  const [holidays, setHolidays] = useState(null)
  const [day, setDay] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [verify, setVerify] = useState(null)
  const [sweep, setSweep] = useState(null)

  const load = useCallback(() => api('/holidays').then(setHolidays).catch(setError), [])
  useEffect(() => {
    load()
  }, [load])

  async function add(e) {
    e.preventDefault()
    setError(null)
    try {
      await api('/holidays', { method: 'POST', body: { day, name } })
      setDay('')
      setName('')
      load()
    } catch (err) {
      setError(err)
    }
  }

  async function remove(d) {
    if (!window.confirm(`Remove the holiday on ${d}? Deadlines will be recalculated.`)) return
    try {
      await api(`/holidays/${d}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="lg:col-span-2">
        <h1 className="text-xl font-semibold tracking-tight">Holidays</h1>
        <p className="mb-4 text-sm text-slate-500">
          Nobody works on these days, so they do not count towards any deadline. Add festival holidays here as they are announced.
        </p>
        <ErrorBanner error={error} onClose={() => setError(null)} />
        <form onSubmit={add} className="my-4 flex flex-wrap items-end gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <Field label="Date">
            <input className={inputClass} type="date" required value={day} onChange={(e) => setDay(e.target.value)} />
          </Field>
          <div className="min-w-48 flex-1">
            <Field label="Name">
              <input className={inputClass} required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Onam" />
            </Field>
          </div>
          <Button variant="primary">Add holiday</Button>
        </form>
        {!holidays ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
            {holidays.map((h) => (
              <li key={h.day} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span>
                  <span className="font-medium">{dayFmt.format(new Date(`${h.day}T00:00:00Z`))}</span>
                  <span className="ml-3 text-slate-500">{h.name}</span>
                </span>
                <button className="text-red-600 hover:underline" onClick={() => remove(h.day)}>Remove</button>
              </li>
            ))}
            {holidays.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">No holidays yet.</li>}
          </ul>
        )}
      </section>

      <aside className="space-y-4">
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="text-sm font-semibold">History integrity</h2>
          <p className="mt-1 text-xs text-slate-500">Checks that no entry of the permanent record has been altered.</p>
          <Button className="mt-3" onClick={() => api('/audit/verify').then(setVerify).catch(setError)}>Verify now</Button>
          {verify && (
            <p className={`mt-3 rounded-lg p-2 text-sm ${verify.intact ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'}`}>
              {verify.intact
                ? `All ${verify.entries_checked} entries are intact.`
                : `Entry #${verify.first_broken_seq} does not match its checksum.`}
            </p>
          )}
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="text-sm font-semibold">Run housekeeping</h2>
          <p className="mt-1 text-xs text-slate-500">
            Runs automatically every minute: closes silent tickets and records missed deadlines.
          </p>
          <Button className="mt-3" onClick={() => api('/ops/housekeeping', { method: 'POST' }).then(setSweep).catch(setError)}>Run now</Button>
          {sweep && (
            <p className="mt-3 rounded-lg bg-slate-100 p-2 text-sm text-slate-700">
              Closed {sweep.auto_closed_waiting} silent and {sweep.auto_closed_resolved} resolved; logged {sweep.breaches_logged} missed deadlines.
            </p>
          )}
        </div>
      </aside>
    </div>
  )
}
