import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import { AUTH_EXPIRED_EVENT, authApi } from '../api/client'
import type { Account } from '../api/types'
import { Landing } from './Landing'

interface AuthContextValue {
  account: Account
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

// eslint-disable-next-line react-refresh/only-export-components -- hook co-located with its context
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}

// Only an authenticated state mounts the app's queries and EventSources;
// any 401 unmounts them, closing every stream.
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

  useEffect(() => {
    const expire = () => setAccount(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, expire)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expire)
  }, [])

  const signOut = useCallback(async () => {
    await authApi.logout().catch(() => undefined)
    setAccount(null)
  }, [])

  if (loading) return null
  if (!account) return <Landing onSignedIn={setAccount} />
  return <AuthContext.Provider value={{ account, signOut }}>{children}</AuthContext.Provider>
}
