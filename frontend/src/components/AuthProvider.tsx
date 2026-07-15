import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import { authApi } from '../api/client'
import { onAuthExpired } from '../api/authEvents'
import type { Account } from '../api/types'
import { Landing } from './Landing'

interface AuthContextValue {
  account: Account
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}

// Sits above the app: only an authenticated state mounts the application's
// queries and EventSources, and any 401 (client or SSE recheck) unmounts them
// — which closes every stream.
export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void authApi
      .session()
      .then((current) => {
        if (!cancelled) setAccount(current)
      })
      .catch(() => {
        // Network trouble reads as signed out; the landing retries via login.
        if (!cancelled) setAccount(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => onAuthExpired(() => setAccount(null)), [])

  const signOut = useCallback(async () => {
    await authApi.logout().catch(() => undefined)
    setAccount(null)
  }, [])

  if (loading) return null
  if (!account) return <Landing onSignedIn={setAccount} />
  return <AuthContext.Provider value={{ account, signOut }}>{children}</AuthContext.Provider>
}
