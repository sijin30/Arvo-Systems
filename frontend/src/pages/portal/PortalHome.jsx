import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api.js'
import { useAuth } from '../../auth.jsx'
import { Badge, ErrorBanner, PriorityBadge, Spinner } from '../../components.jsx'
import { CUSTOMER_STATUS, fmtShort } from '../../format.js'

export default function PortalHome() {
  const { customer } = useAuth()
  const [tickets, setTickets] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    api('/portal/tickets').then((t) => { setTickets(t); setError(null) }).catch(setError)
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load])

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Hello, {customer.name.split(' ')[0]}</h1>
          <p className="text-sm text-slate-500">Your support requests to Arvo Systems.</p>
        </div>
        <Link to="/new" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500">
          Report a problem
        </Link>
      </div>

      <ErrorBanner error={error} onClose={() => setError(null)} />

      {!tickets ? (
        <Spinner />
      ) : tickets.length === 0 ? (
        <div className="rounded-xl bg-white p-10 text-center ring-1 ring-slate-200">
          <p className="font-medium text-slate-800">No requests yet</p>
          <p className="mt-1 text-sm text-slate-500">When something goes wrong, tell us here and an agent will pick it up.</p>
          <Link to="/new" className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:underline">Report a problem</Link>
        </div>
      ) : (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
          {tickets.map((t) => (
            <li key={t.id}>
              <Link to={`/tickets/${t.id}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 hover:bg-slate-50">
                <span>
                  <span className="mr-2 font-mono text-xs text-slate-500">{t.reference}</span>
                  <span className="font-medium text-slate-900">{t.subject}</span>
                  <span className="mt-0.5 block text-xs text-slate-500">Updated {fmtShort(t.updated_at)}</span>
                </span>
                <span className="flex items-center gap-2">
                  <PriorityBadge priority={t.priority} />
                  <Badge tone={CUSTOMER_STATUS[t.status][1]}>{CUSTOMER_STATUS[t.status][0]}</Badge>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
