import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, download } from '../api.js'
import { Button, ErrorBanner, PriorityBadge, SlaChip, Spinner, StatusBadge, inputClass } from '../components.jsx'
import { fmtShort } from '../format.js'

const VIEWS = [
  { key: 'active', label: 'All active' },
  { key: 'unassigned', label: 'Unassigned' },
  { key: 'late', label: 'Late' },
  { key: 'waiting', label: 'Waiting on customer' },
  { key: 'history', label: 'Resolved & closed' },
]

function Stat({ label, value, tone, onClick, active }) {
  const tones = {
    red: 'text-red-600',
    blue: 'text-sky-600',
    indigo: 'text-indigo-600',
    slate: 'text-slate-900',
  }
  return (
    <button
      onClick={onClick}
      className={`rounded-xl bg-white p-4 text-left shadow-sm ring-1 transition hover:ring-indigo-300 ${active ? 'ring-2 ring-indigo-500' : 'ring-slate-200'}`}
    >
      <div className={`text-3xl font-semibold tabular-nums ${tones[tone]}`}>{value ?? '–'}</div>
      <div className="mt-1 text-sm text-slate-500">{label}</div>
    </button>
  )
}

export default function Dashboard() {
  const [params, setParams] = useSearchParams()
  const scope = params.get('scope') === 'all' ? 'all' : 'mine'
  const view = VIEWS.some((v) => v.key === params.get('view')) ? params.get('view') : 'active'
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [list, setList] = useState(null)
  const [counts, setCounts] = useState(null)
  const [error, setError] = useState(null)

  const set = (patch) => {
    const next = new URLSearchParams(params)
    Object.entries(patch).forEach(([k, v]) => next.set(k, v))
    setParams(next, { replace: true })
  }

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])

  const load = useCallback(async () => {
    try {
      const query = new URLSearchParams({ scope, view, limit: '100' })
      if (debouncedQ) query.set('q', debouncedQ)
      const [l, c] = await Promise.all([api(`/tickets?${query}`), api(`/tickets/counts?scope=${scope}`)])
      setList(l)
      setCounts(c)
      setError(null)
    } catch (e) {
      setError(e)
    }
  }, [scope, view, debouncedQ])

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{scope === 'mine' ? 'My tickets' : 'All tickets'}</h1>
          <p className="text-sm text-slate-500">Deadlines count working hours only: Mon–Fri, 9:30 am–6:30 pm, excluding holidays.</p>
        </div>
        <div className="inline-flex rounded-lg bg-slate-200/70 p-0.5 text-sm font-medium">
          {['mine', 'all'].map((s) => (
            <button
              key={s}
              onClick={() => set({ scope: s })}
              className={`rounded-md px-3 py-1.5 ${scope === s ? 'bg-white shadow-sm' : 'text-slate-600'}`}
            >
              {s === 'mine' ? 'Mine' : 'Everyone'}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Active tickets" value={counts?.active} tone="slate" active={view === 'active'} onClick={() => set({ view: 'active' })} />
        <Stat label="Unassigned" value={counts?.unassigned} tone="indigo" active={view === 'unassigned'} onClick={() => set({ view: 'unassigned' })} />
        <Stat label="Already late" value={counts?.late} tone="red" active={view === 'late'} onClick={() => set({ view: 'late' })} />
        <Stat label="Waiting on customer" value={counts?.waiting_on_customer} tone="blue" active={view === 'waiting'} onClick={() => set({ view: 'waiting' })} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              onClick={() => set({ view: v.key })}
              className={`rounded-full px-3 py-1 text-sm font-medium ${view === v.key ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:text-slate-900'}`}
            >
              {v.label}
            </button>
          ))}
        </div>
        <div className="w-64">
          <input
            className={inputClass}
            placeholder="Search ref, subject or customer"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search tickets"
          />
        </div>
        <Button
          className="ml-auto"
          onClick={() =>
            download(`/tickets/export.csv?scope=${scope}&view=${view}`, 'tickets.csv').catch(setError)
          }
          title="Customer-safe: contains no message text"
        >
          Export CSV
        </Button>
      </div>

      <ErrorBanner error={error} onClose={() => setError(null)} />

      {!list ? (
        <Spinner />
      ) : list.items.length === 0 ? (
        <div className="rounded-xl bg-white p-10 text-center text-slate-500 ring-1 ring-slate-200">
          Nothing here. {view === 'active' && scope === 'mine' && 'Take a ticket from the Unassigned tab.'}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Ticket</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Reply</th>
                <th className="px-4 py-3">Fix</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.items.map((t) => (
                <tr key={t.id} className={t.late ? 'bg-red-50/50' : ''}>
                  <td className="max-w-md px-4 py-3">
                    <Link to={`/tickets/${t.id}`} className="font-medium text-slate-900 hover:text-indigo-700">
                      <span className="mr-2 font-mono text-xs text-slate-500">{t.reference}</span>
                      {t.subject}
                    </Link>
                    <div className="text-xs text-slate-500">{t.customer.name}</div>
                  </td>
                  <td className="px-4 py-3"><PriorityBadge priority={t.priority} /></td>
                  <td className="px-4 py-3"><StatusBadge status={t.status} /></td>
                  <td className="px-4 py-3"><SlaChip metric={t.sla.response} /></td>
                  <td className="px-4 py-3"><SlaChip metric={t.sla.resolution} /></td>
                  <td className="px-4 py-3 text-slate-600">{t.assignee?.name ?? <span className="text-slate-400">Unassigned</span>}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">{fmtShort(t.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
            {list.total} ticket{list.total === 1 ? '' : 's'}
            {list.total > list.items.length && ` (showing ${list.items.length})`} · refreshes every 30 seconds
          </div>
        </div>
      )}
    </div>
  )
}
