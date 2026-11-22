import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api.js'
import { Badge, Button, ErrorBanner, PriorityBadge, Spinner, inputClass } from '../../components.jsx'
import { CUSTOMER_STATUS, fmtFull, fmtShort } from '../../format.js'

export default function PortalTicket() {
  const { id } = useParams()
  const [ticket, setTicket] = useState(null)
  const [body, setBody] = useState('')
  const [reopening, setReopening] = useState(false)
  const [reopenText, setReopenText] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api(`/portal/tickets/${id}`).then((t) => { setTicket(t); setError(null) }).catch(setError)
  }, [id])

  useEffect(() => {
    load()
    const timer = setInterval(load, 20000)
    return () => clearInterval(timer)
  }, [load])

  async function run(path, payload) {
    setBusy(true)
    setError(null)
    try {
      setTicket(await api(`/portal/tickets/${id}${path}`, { method: 'POST', body: payload }))
      return true
    } catch (e) {
      setError(e)
      load()
      return false
    } finally {
      setBusy(false)
    }
  }

  if (!ticket) return error ? <ErrorBanner error={error.status === 404 ? 'We could not find that ticket.' : error} /> : <Spinner />
  const [statusText, tone] = CUSTOMER_STATUS[ticket.status]

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <Link to="/" className="text-sm text-indigo-600 hover:underline">← My requests</Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-slate-500">{ticket.reference}</span>
          <h1 className="text-xl font-semibold tracking-tight">{ticket.subject}</h1>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Badge tone={tone}>{statusText}</Badge>
          <PriorityBadge priority={ticket.priority} />
          <span className="text-xs text-slate-500">Opened {fmtShort(ticket.created_at)}</span>
        </div>
      </div>

      <ErrorBanner error={error} onClose={() => setError(null)} />

      <div className="space-y-3">
        {ticket.messages.map((m) => (
          <div key={m.id} className={`flex ${m.sender === 'you' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl p-4 ring-1 ${m.sender === 'you' ? 'bg-indigo-50 ring-indigo-200' : 'bg-white ring-slate-200'}`}>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{m.sender === 'you' ? 'You' : 'Arvo Support'}</div>
              <p className="whitespace-pre-wrap text-sm">{m.body}</p>
              <div className="mt-2 text-xs text-slate-500">{fmtShort(m.created_at)}</div>
            </div>
          </div>
        ))}
      </div>

      {ticket.status === 'waiting_for_you' && (
        <p className="rounded-lg bg-sky-50 p-3 text-sm text-sky-800">We asked you a question. Please reply below so we can continue.</p>
      )}

      {ticket.can_reply && (
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <textarea className={inputClass} rows={4} maxLength={10000} placeholder="Write a message to the support team…" value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="mt-3 flex justify-end">
            <Button
              variant="primary"
              disabled={busy || !body.trim()}
              onClick={async () => { if (await run('/messages', { body: body.trim() })) setBody('') }}
            >
              Send message
            </Button>
          </div>
        </div>
      )}

      {ticket.status === 'resolved' && (
        <div className="space-y-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <p className="text-sm text-slate-700">We have marked this as resolved.</p>
          {ticket.can_reopen ? (
            !reopening ? (
              <>
                <Button onClick={() => setReopening(true)}>It is not fixed: reopen</Button>
                <p className="text-xs text-slate-500">You can reopen this until {fmtFull(ticket.reopen_until)}.</p>
              </>
            ) : (
              <div className="space-y-2">
                <textarea className={inputClass} rows={3} placeholder="What is still wrong? (optional)" value={reopenText} onChange={(e) => setReopenText(e.target.value)} />
                <div className="flex gap-2">
                  <Button variant="primary" disabled={busy} onClick={async () => { if (await run('/reopen', { message: reopenText.trim() || null })) { setReopening(false); setReopenText('') } }}>
                    Reopen ticket
                  </Button>
                  <Button onClick={() => setReopening(false)}>Cancel</Button>
                </div>
              </div>
            )
          ) : (
            <p className="text-sm text-slate-600">
              The time to reopen this has passed. If the problem is back, please{' '}
              <Link to="/new" className="font-medium text-indigo-600 hover:underline">report it as a new request</Link>.
            </p>
          )}
        </div>
      )}

      {ticket.status === 'closed' && (
        <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-700">
          This request is closed. If you still need help, please{' '}
          <Link to="/new" className="font-medium text-indigo-600 hover:underline">report a new problem</Link>.
        </p>
      )}
    </div>
  )
}
