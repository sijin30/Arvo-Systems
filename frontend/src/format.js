// Arvo works in India Standard Time; every timestamp is shown in IST.
const TZ = 'Asia/Kolkata'
const WORKDAY_SECONDS = 9 * 3600

const shortFmt = new Intl.DateTimeFormat('en-IN', {
  timeZone: TZ, day: '2-digit', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
})
const fullFmt = new Intl.DateTimeFormat('en-IN', {
  timeZone: TZ, day: '2-digit', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true,
})

export const fmtShort = (iso) => (iso ? shortFmt.format(new Date(iso)) : '—')
export const fmtFull = (iso) => (iso ? `${fullFmt.format(new Date(iso))} IST` : '—')

// Durations are working time: one "d" is a 9-hour working day.
export function fmtDuration(seconds) {
  const s = Math.abs(Math.round(seconds))
  const d = Math.floor(s / WORKDAY_SECONDS)
  const h = Math.floor((s % WORKDAY_SECONDS) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const parts = []
  if (d) parts.push(`${d}d`)
  if (h) parts.push(`${h}h`)
  if (m && parts.length < 2) parts.push(`${m}m`)
  return parts.length ? parts.slice(0, 2).join(' ') : '<1m'
}

export const STATUS_LABEL = {
  new: 'New',
  open: 'Open',
  waiting_customer: 'Waiting on customer',
  resolved: 'Resolved',
  closed: 'Closed',
}

export const PRIORITY_LABEL = { urgent: 'Urgent', medium: 'Medium', low: 'Low' }

const ACTION_LABEL = {
  'ticket.created': 'Ticket created',
  'ticket.claimed': 'Ticket taken',
  'ticket.released': 'Ticket released',
  'ticket.assigned': 'Ticket assigned',
  'message.public_reply': 'Reply sent to customer',
  'message.internal_note': 'Private team note added',
  'message.customer_message': 'Customer message logged',
  'ticket.waiting_customer': 'Waiting on customer (clock paused)',
  'ticket.customer_replied': 'Customer replied (clock resumed)',
  'ticket.resolved': 'Marked resolved',
  'ticket.reopened': 'Reopened',
  'ticket.priority_changed': 'Priority changed',
  'ticket.auto_closed': 'Closed automatically',
  'sla.response_breached': 'Reply deadline missed',
  'sla.resolution_breached': 'Fix deadline missed',
}
export const actionLabel = (a) => ACTION_LABEL[a] || a
