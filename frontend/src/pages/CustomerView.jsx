import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, ErrorBanner, Spinner } from '../components.jsx'
import { CUSTOMER_STATUS as STATUS, fmtShort } from '../format.js'

/** What the customer sees. It is fed only by the public API, which never returns private notes. */
export default function CustomerView() {
  const { token } = useParams()
  const [ticket, setTicket] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api(`/public/tickets/${encodeURIComponent(token)}`).then(setTicket).catch(setError)
  }, [token])

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-6 flex items-center gap-2 text-lg font-semibold">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-indigo-600 text-sm text-white">F</span>
        Arvo Support
      </div>
      {error && <ErrorBanner error={error.status === 404 ? 'We could not find that ticket.' : error} />}
      {!ticket && !error && <Spinner />}
      {ticket && (
        <div className="space-y-4">
          <div>
            <div className="font-mono text-sm text-slate-500">{ticket.reference}</div>
            <h1 className="text-xl font-semibold tracking-tight">{ticket.subject}</h1>
            <div className="mt-2"><Badge tone={STATUS[ticket.status][1]}>{STATUS[ticket.status][0]}</Badge></div>
          </div>
          {ticket.messages.map((m) => (
            <div key={m.id} className={`flex ${m.sender === 'you' ? 'justify-start' : 'justify-end'}`}>
              <div className={`max-w-[85%] rounded-xl p-4 ring-1 ${m.sender === 'you' ? 'bg-white ring-slate-200' : 'bg-indigo-50 ring-indigo-200'}`}>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{m.sender === 'you' ? 'You' : 'Arvo Support'}</div>
                <p className="whitespace-pre-wrap text-sm">{m.body}</p>
                <div className="mt-2 text-xs text-slate-500">{fmtShort(m.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
