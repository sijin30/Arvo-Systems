import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Button, ErrorBanner, PriorityBadge, SlaChip, Spinner, StatusBadge, inputClass } from '../components.jsx'
import { PRIORITY_LABEL, actionLabel, fmtFull, fmtShort } from '../format.js'

const MODES = {
  reply: {
    tab: 'Reply to customer',
    ring: 'ring-indigo-300 focus-within:ring-indigo-500',
    banner: 'bg-indigo-50 text-indigo-800',
    hint: 'The customer WILL see this message.',
    button: 'Send to customer',
    variant: 'primary',
  },
  note: {
    tab: 'Private team note',
    ring: 'ring-amber-300 focus-within:ring-amber-500',
    banner: 'bg-amber-50 text-amber-900',
    hint: 'Only your team can see this. It is never sent to the customer.',
    button: 'Save private note',
    variant: 'amber',
  },
  customer: {
    tab: "Log customer's message",
    ring: 'ring-slate-300 focus-within:ring-slate-500',
    banner: 'bg-slate-100 text-slate-700',
    hint: "Record something the customer told you. If we were waiting for them, the SLA clock starts again.",
    button: 'Log customer message',
    variant: 'default',
  },
}

const CLOSE_TEXT = {
  customer_inactive: 'Closed automatically: the customer did not reply for a working week.',
  reopen_window_expired: 'Closed automatically: the reopen window (a working week) ended.',
}

function Message({ m }) {
  if (m.kind === 'internal_note') {
    return (
      <div className="rounded-xl border border-dashed border-amber-400 bg-amber-50 p-4">
        <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-800">
          <span aria-hidden>🔒</span> Private team note · never shown to the customer
        </div>
        <p className="whitespace-pre-wrap text-sm text-amber-950">{m.body}</p>
        <div className="mt-2 text-xs text-amber-800/80">{m.author?.name} · {fmtShort(m.created_at)}</div>
      </div>
    )
  }
  const mine = m.kind === 'public_reply'
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-xl p-4 ring-1 ${mine ? 'bg-indigo-50 ring-indigo-200' : 'bg-white ring-slate-200'}`}>
        <div className={`mb-1 text-xs font-semibold uppercase tracking-wide ${mine ? 'text-indigo-700' : 'text-slate-500'}`}>
          {mine ? 'Sent to customer' : 'From the customer'}
        </div>
        <p className="whitespace-pre-wrap text-sm">{m.body}</p>
        <div className="mt-2 text-xs text-slate-500">
          {mine ? m.author?.name : m.author ? `logged by ${m.author.name}` : ''} {mine || m.author ? '· ' : ''}
          {fmtShort(m.created_at)}
        </div>
      </div>
    </div>
  )
}

function Composer({ ticket, onSend, busy }) {
  const a = ticket.actions
  const [mode, setMode] = useState(a.can_reply ? 'reply' : 'note')
  const [body, setBody] = useState('')
  const [waiting, setWaiting] = useState(false)
  const allowed = { reply: a.can_reply, note: a.can_note, customer: a.can_log_customer_reply }

  let blocked = null
  if (!allowed[mode]) {
    if (ticket.status === 'new') blocked = 'Take this ticket first.'
    else if (ticket.status === 'resolved') blocked = 'This ticket is resolved. Reopen it to continue.'
    else if (ticket.status === 'closed') blocked = 'This ticket is closed.'
    else blocked = `Only ${ticket.assignee?.name ?? 'the assigned agent'} can do this.`
  }
  const m = MODES[mode]

  async function send() {
    const ok = await onSend({ kind: { reply: 'public_reply', note: 'internal_note', customer: 'customer_message' }[mode], body, set_waiting: mode === 'reply' && waiting })
    if (ok) {
      setBody('')
      setWaiting(false)
    }
  }

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div role="tablist" className="mb-3 flex flex-wrap gap-1">
        {Object.entries(MODES).map(([key, def]) => (
          <button
            key={key}
            role="tab"
            aria-selected={mode === key}
            onClick={() => setMode(key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${mode === key ? def.banner + ' ring-1 ring-inset ring-current/20' : 'text-slate-500 hover:text-slate-800'}`}
          >
            {def.tab}
          </button>
        ))}
      </div>
      <div className={`mb-2 rounded-lg px-3 py-2 text-sm font-medium ${m.banner}`}>{mode === 'note' && '🔒 '}{m.hint}</div>
      {blocked ? (
        <p className="py-3 text-sm text-slate-500">{blocked}</p>
      ) : (
        <>
          <textarea
            className={`${inputClass} ring-2 ${m.ring}`}
            rows={4}
            maxLength={10000}
            placeholder={mode === 'note' ? 'Write a note for your team…' : mode === 'reply' ? 'Write your reply to the customer…' : 'What did the customer say?'}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            {mode === 'reply' ? (
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={waiting} onChange={(e) => setWaiting(e.target.checked)} />
                I am waiting for the customer&apos;s answer <span className="text-slate-500">(pauses the SLA clock)</span>
              </label>
            ) : (
              <span />
            )}
            <Button variant={m.variant} disabled={busy || !body.trim()} onClick={send}>
              {m.button}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function SlaRow({ label, metric, hint }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2">
      <div>
        <div className="text-sm font-medium text-slate-700">{label}</div>
        <div className="text-xs text-slate-500">{metric.due_at ? `Due ${fmtFull(metric.due_at)}` : hint}</div>
      </div>
      <SlaChip metric={metric} />
    </div>
  )
}

export default function Ticket() {
  const { id } = useParams()
  const { agent } = useAuth()
  const [ticket, setTicket] = useState(null)
  const [audit, setAudit] = useState([])
  const [agents, setAgents] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [panel, setPanel] = useState(null) // 'resolve' | 'reopen'
  const [panelText, setPanelText] = useState('')
  const [assignTo, setAssignTo] = useState('')
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([api(`/tickets/${id}`), api(`/tickets/${id}/audit`)])
      setTicket(t)
      setAudit(a)
    } catch (e) {
      setError(e)
    }
  }, [id])

  useEffect(() => {
    load()
    const timer = setInterval(load, 20000)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    if (agent.role === 'lead') api('/agents').then(setAgents).catch(() => {})
  }, [agent.role])

  async function run(path, body) {
    setBusy(true)
    setError(null)
    try {
      const t = await api(`/tickets/${id}${path}`, { method: 'POST', body: body ?? {} })
      setTicket(t)
      setAudit(await api(`/tickets/${id}/audit`))
      return true
    } catch (e) {
      setError(e)
      load() // somebody else may have changed the ticket: show the truth
      return false
    } finally {
      setBusy(false)
    }
  }

  if (!ticket) return error ? <ErrorBanner error={error} /> : <Spinner />
  const a = ticket.actions
  const sla = ticket.sla
  const followUp = `/new?related=${ticket.id}&name=${encodeURIComponent(ticket.customer.name)}&email=${encodeURIComponent(ticket.customer.email)}`

  return (
    <div className="space-y-4">
      <div>
        <Link to="/" className="text-sm text-indigo-600 hover:underline">← All tickets</Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-slate-500">{ticket.reference}</span>
          <h1 className="text-xl font-semibold tracking-tight">{ticket.subject}</h1>
          <PriorityBadge priority={ticket.priority} />
          <StatusBadge status={ticket.status} />
          {ticket.late && <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">LATE</span>}
        </div>
        {ticket.related_reference && (
          <p className="mt-1 text-sm text-slate-500">
            Follow-up to <Link className="text-indigo-600 hover:underline" to={`/tickets/${ticket.related_ticket_id}`}>{ticket.related_reference}</Link>
          </p>
        )}
      </div>

      <ErrorBanner error={error} onClose={() => setError(null)} />

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="space-y-3 lg:col-span-2">
          {ticket.messages.map((m) => <Message key={m.id} m={m} />)}
          <Composer
            ticket={ticket}
            busy={busy}
            onSend={(payload) => run('/messages', payload)}
          />
        </section>

        <aside className="space-y-4">
          <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <h2 className="text-sm font-semibold text-slate-900">Deadlines</h2>
            <div className="divide-y divide-slate-100">
              <SlaRow label="First reply" metric={sla.response} hint="Clock stopped" />
              <SlaRow label="Fix" metric={sla.resolution} hint="Clock stopped" />
            </div>
            {sla.waiting_on_customer && (
              <p className="mt-2 rounded-lg bg-sky-50 p-2 text-xs text-sky-800">
                Waiting on the customer, so the clock is paused. It closes by itself on {fmtFull(sla.auto_close_at)} if they stay silent.
              </p>
            )}
            {sla.reopen_until && (
              <p className="mt-2 rounded-lg bg-slate-100 p-2 text-xs text-slate-700">
                The customer can reopen this ticket until {fmtFull(sla.reopen_until)}.
              </p>
            )}
            {ticket.status === 'closed' && ticket.closed_reason && (
              <p className="mt-2 rounded-lg bg-slate-100 p-2 text-xs text-slate-700">{CLOSE_TEXT[ticket.closed_reason]}</p>
            )}
            <p className="mt-2 text-xs text-slate-400">Durations are working time (1d = 9h).</p>
          </div>

          <div className="space-y-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <h2 className="text-sm font-semibold text-slate-900">Actions</h2>
            <dl className="text-sm">
              <div className="flex justify-between py-0.5"><dt className="text-slate-500">Owner</dt><dd>{ticket.assignee?.name ?? 'Unassigned'}</dd></div>
              <div className="flex justify-between py-0.5"><dt className="text-slate-500">Customer</dt><dd className="text-right">{ticket.customer.name}<br /><span className="text-xs text-slate-500">{ticket.customer.email}</span></dd></div>
              <div className="flex justify-between py-0.5"><dt className="text-slate-500">Created</dt><dd>{fmtShort(ticket.created_at)}</dd></div>
              {ticket.reopen_count > 0 && <div className="flex justify-between py-0.5"><dt className="text-slate-500">Reopened</dt><dd>{ticket.reopen_count}×</dd></div>}
            </dl>
            <div className="flex flex-wrap gap-2">
              {a.can_claim && <Button variant="primary" disabled={busy} onClick={() => run('/claim')}>Take this ticket</Button>}
              {a.can_release && <Button disabled={busy} onClick={() => run('/release')}>Release</Button>}
              {a.can_resolve && <Button disabled={busy} onClick={() => { setPanel('resolve'); setPanelText('') }}>Resolve…</Button>}
              {a.can_reopen && <Button disabled={busy} onClick={() => { setPanel('reopen'); setPanelText('') }}>Reopen…</Button>}
              {(ticket.status === 'closed' || (ticket.status === 'resolved' && !a.can_reopen)) && (
                <Link to={followUp} className="inline-flex items-center rounded-lg bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50">
                  Create follow-up ticket
                </Link>
              )}
            </div>
            {panel && (
              <div className="space-y-2 rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-600">
                  {panel === 'resolve'
                    ? 'Add a final message for the customer (required if you have not replied yet).'
                    : "Optionally record what the customer said. They have a working week from resolution to reopen."}
                </p>
                <textarea className={inputClass} rows={3} value={panelText} onChange={(e) => setPanelText(e.target.value)} placeholder={panel === 'resolve' ? 'Message to the customer (visible to them)' : "Customer's message"} />
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    disabled={busy}
                    onClick={async () => {
                      if (await run(panel === 'resolve' ? '/resolve' : '/reopen', { message: panelText.trim() || null })) setPanel(null)
                    }}
                  >
                    {panel === 'resolve' ? 'Resolve ticket' : 'Reopen ticket'}
                  </Button>
                  <Button onClick={() => setPanel(null)}>Cancel</Button>
                </div>
              </div>
            )}
            {a.can_change_priority && (
              <label className="block text-sm">
                <span className="mb-1 block text-slate-500">Priority</span>
                <select
                  className={inputClass}
                  value={ticket.priority}
                  disabled={busy}
                  onChange={(e) => {
                    const next = e.target.value
                    if (next !== ticket.priority && window.confirm(`Change priority to ${PRIORITY_LABEL[next]}? Deadlines are recalculated from the time the ticket was created.`)) {
                      run('/priority', { priority: next })
                    }
                  }}
                >
                  {Object.entries(PRIORITY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
            )}
            {a.can_assign && (
              <div className="flex gap-2">
                <select className={inputClass} value={assignTo} onChange={(e) => setAssignTo(e.target.value)} aria-label="Assign to">
                  <option value="">Assign to…</option>
                  {agents.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
                <Button disabled={busy || !assignTo} onClick={() => run('/assign', { agent_id: Number(assignTo) })}>Assign</Button>
              </div>
            )}
            <button
              className="text-xs text-slate-500 hover:text-indigo-700 hover:underline"
              onClick={() => {
                navigator.clipboard?.writeText(`${window.location.origin}/t/${ticket.public_token}`).then(() => {
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }).catch(() => {})
              }}
            >
              {copied ? 'Copied!' : 'Copy customer view link (shows no private notes)'}
            </button>
          </div>

          <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <h2 className="mb-2 text-sm font-semibold text-slate-900">History</h2>
            <ol className="space-y-3 border-l border-slate-200 pl-4">
              {[...audit].reverse().map((e) => (
                <li key={e.seq} className="relative text-sm">
                  <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-slate-400" />
                  <div className="font-medium text-slate-800">{actionLabel(e.action)}</div>
                  <div className="text-xs text-slate-500">
                    {e.actor_type === 'system' ? 'System' : e.actor_name} · {fmtFull(e.occurred_at)}
                  </div>
                  {e.action === 'ticket.priority_changed' && <div className="text-xs text-slate-500">{e.details.from} → {e.details.to}</div>}
                  {e.action.startsWith('sla.') && <div className="text-xs text-slate-500">Was due {fmtFull(e.details.due_at)}</div>}
                </li>
              ))}
            </ol>
            <p className="mt-3 text-xs text-slate-400">This record is permanent: entries cannot be edited or removed.</p>
          </div>
        </aside>
      </div>
    </div>
  )
}
