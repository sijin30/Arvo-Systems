import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import { Spinner } from './components.jsx'
import Account from './pages/Account.jsx'
import Admin from './pages/Admin.jsx'
import CustomerView from './pages/CustomerView.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import NewTicket from './pages/NewTicket.jsx'
import PortalHome from './pages/portal/PortalHome.jsx'
import PortalNew from './pages/portal/PortalNew.jsx'
import PortalTicket from './pages/portal/PortalTicket.jsx'
import Team from './pages/Team.jsx'
import Ticket from './pages/Ticket.jsx'

const navClass = ({ isActive }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:text-slate-900'}`

function Shell({ links, children }) {
  const { user, kind, logout } = useAuth()
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <span className="flex items-center gap-2 text-lg font-semibold tracking-tight text-slate-900">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-indigo-600 text-sm text-white">F</span>
            Frontdesk
          </span>
          <nav className="flex flex-wrap items-center gap-1">
            {links.map(([to, label, end]) => (
              <NavLink key={to} to={to} end={end} className={navClass}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {user.name}
              {user.role === 'lead' && <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">lead</span>}
              {kind === 'customer' && <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">customer</span>}
            </span>
            <button onClick={logout} className="font-medium text-indigo-600 hover:underline">
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      {/* What a customer sees via a shared link: no login, and the API behind it never returns private notes. */}
      <Route path="/t/:token" element={<CustomerView />} />
      <Route path="*" element={<Signed />} />
    </Routes>
  )
}

function Signed() {
  const { kind, user, ready } = useAuth()
  if (!ready) return <Spinner />
  if (!user) return <Login />
  return kind === 'customer' ? <CustomerApp /> : <StaffApp />
}

function CustomerApp() {
  return (
    <Shell
      links={[
        ['/', 'My requests', true],
        ['/new', 'Report a problem'],
        ['/account', 'Account'],
      ]}
    >
      <Routes>
        <Route path="/" element={<PortalHome />} />
        <Route path="/new" element={<PortalNew />} />
        <Route path="/tickets/:id" element={<PortalTicket />} />
        <Route path="/account" element={<Account />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}

function StaffApp() {
  const { agent } = useAuth()
  const lead = agent.role === 'lead'
  return (
    <Shell
      links={[
        ['/', 'Tickets', true],
        ['/new', 'New ticket'],
        ...(lead ? [['/team', 'Team'], ['/admin', 'Admin']] : []),
        ['/account', 'Account'],
      ]}
    >
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/new" element={<NewTicket />} />
        <Route path="/tickets/:id" element={<Ticket />} />
        <Route path="/account" element={<Account />} />
        <Route path="/team" element={lead ? <Team /> : <Navigate to="/" replace />} />
        <Route path="/admin" element={lead ? <Admin /> : <Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}
