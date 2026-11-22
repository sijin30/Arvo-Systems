import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, loadKind, loadToken, setToken, setUnauthorizedHandler } from './api.js'

const AuthContext = createContext(null)

/**
 * Two kinds of people sign in: support staff ("agent", which includes the lead) and
 * customers. `kind` says which; `user` is the profile the server returned.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [kind, setKind] = useState(null)
  const [ready, setReady] = useState(false)
  const navigate = useNavigate()

  // Back to the start page, so the next person who signs in does not land on the last ticket.
  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    setKind(null)
    navigate('/', { replace: true })
  }, [navigate])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    const saved = loadKind()
    if (!loadToken() || (saved !== 'agent' && saved !== 'customer')) {
      setToken(null)
      setReady(true)
      return
    }
    api(saved === 'agent' ? '/auth/me' : '/portal/me')
      .then((u) => {
        setUser(u)
        setKind(saved)
      })
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [logout])

  const loginAgent = useCallback(async (email, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } })
    setToken(data.token, 'agent')
    setUser(data.agent)
    setKind('agent')
  }, [])

  const loginCustomer = useCallback(async (email, password) => {
    const data = await api('/portal/login', { method: 'POST', body: { email, password } })
    setToken(data.token, 'customer')
    setUser(data.customer)
    setKind('customer')
  }, [])

  const signupCustomer = useCallback(async (name, email, password) => {
    const data = await api('/portal/signup', { method: 'POST', body: { name, email, password } })
    setToken(data.token, 'customer')
    setUser(data.customer)
    setKind('customer')
  }, [])

  const value = {
    user,
    kind,
    ready,
    agent: kind === 'agent' ? user : null,
    customer: kind === 'customer' ? user : null,
    loginAgent,
    loginCustomer,
    signupCustomer,
    logout,
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)
