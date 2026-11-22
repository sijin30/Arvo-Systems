import { PRIORITY_LABEL, STATUS_LABEL, fmtDuration, fmtFull } from './format.js'

const TONES = {
  red: 'bg-red-50 text-red-700 ring-red-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/25',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  blue: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  slate: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
}

export function Badge({ tone = 'slate', children, title }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  )
}

const PRIORITY_TONE = { urgent: 'red', medium: 'amber', low: 'slate' }
export const PriorityBadge = ({ priority }) => (
  <Badge tone={PRIORITY_TONE[priority]}>{PRIORITY_LABEL[priority]}</Badge>
)

const STATUS_TONE = { new: 'indigo', open: 'green', waiting_customer: 'blue', resolved: 'slate', closed: 'slate' }
export const StatusBadge = ({ status }) => <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>

/** One SLA promise (reply or fix) as a short coloured chip. All durations are working time. */
export function SlaChip({ metric }) {
  const due = metric.due_at ? `Due ${fmtFull(metric.due_at)}` : 'Clock stopped'
  switch (metric.state) {
    case 'breached':
      return (
        <Badge tone="red" title={due}>
          Late {fmtDuration(metric.remaining_seconds)}
        </Badge>
      )
    case 'running': {
      const tight = metric.remaining_seconds < metric.budget_seconds * 0.25
      return (
        <Badge tone={tight ? 'amber' : 'green'} title={due}>
          {fmtDuration(metric.remaining_seconds)} left
        </Badge>
      )
    }
    case 'paused':
      return (
        <Badge tone="blue" title="Waiting on the customer: the clock is paused">
          Paused
        </Badge>
      )
    case 'met':
      return (
        <Badge tone="green" title={due}>
          Met
        </Badge>
      )
    default:
      return (
        <Badge tone="slate" title="Closed before it was resolved">
          Stopped
        </Badge>
      )
  }
}

export function ErrorBanner({ error, onClose }) {
  if (!error) return null
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <span>{typeof error === 'string' ? error : error.message}</span>
      {onClose && (
        <button onClick={onClose} className="font-medium text-red-700 hover:underline">
          Dismiss
        </button>
      )}
    </div>
  )
}

export const Spinner = ({ label = 'Loading…' }) => (
  <div className="py-16 text-center text-sm text-slate-500">{label}</div>
)

export function Button({ variant = 'default', className = '', ...props }) {
  const styles = {
    default: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50',
    primary: 'bg-indigo-600 text-white hover:bg-indigo-500',
    danger: 'bg-white text-red-700 ring-1 ring-inset ring-red-300 hover:bg-red-50',
    amber: 'bg-amber-500 text-white hover:bg-amber-400',
  }
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center rounded-lg px-3.5 py-2 text-sm font-medium shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  )
}

export const inputClass =
  'block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500'

export const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
    {children}
    {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
  </label>
)
