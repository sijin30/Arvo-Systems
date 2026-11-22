import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, loadToken, setToken, setUnauthorizedHandler } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [agent, setAgent] = useState(null)
  const [ready, setReady] = useState(false)

  const logout = useCallback(() => {
    setToken(null)
    setAgent(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!loadToken()) {
      setReady(true)
      return
    }
    api('/auth/me')
      .then(setAgent)
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [logout])

  const login = useCallback(async (email, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } })
    setToken(data.token)
    setAgent(data.agent)
  }, [])

  return <AuthContext.Provider value={{ agent, ready, login, logout }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)
