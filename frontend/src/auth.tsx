import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchMe, logoutUser, type AuthUser } from './api'

interface AuthState {
  user: AuthUser | null
  signIn: (user: AuthUser) => void
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)
const STORAGE_KEY = 'cc.user'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? (JSON.parse(raw) as AuthUser) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    try {
      if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Ignore storage failures (e.g. private browsing); session stays in memory.
    }
  }, [user])

  // The saved user is only a display hint; the server session (HttpOnly cookie) is the source of truth.
  // On load, confirm it, so an expired session or a login from before sessions existed gets signed out.
  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => {})
  }, [])

  const signOut = () => {
    setUser(null)
    logoutUser().catch(() => {})
  }

  return (
    <AuthContext.Provider value={{ user, signIn: setUser, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
