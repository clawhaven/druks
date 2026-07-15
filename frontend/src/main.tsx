import { StrictMode, useMemo } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { App } from './App'
import { AuthProvider, useAuth } from './components/AuthProvider'
import { UserPreferencesProvider } from './lib/preferences'
import './styles.css'

// Everything that queries the API lives BELOW the auth gate, with a query
// cache scoped to the signed-in account — nothing cached for one account can
// render for the next, and no query fires before a session exists.
function AuthedApp() {
  const { account } = useAuth()
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // SSE delivers freshness; snapshots are explicit refetches.
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000,
          },
        },
      }),
    // A different account gets a fresh, empty cache.
    [account.id],
  )
  return (
    <QueryClientProvider client={queryClient}>
      <UserPreferencesProvider>
        <App />
      </UserPreferencesProvider>
    </QueryClientProvider>
  )
}

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element #root not found')

createRoot(rootElement).render(
  <StrictMode>
    <AuthProvider>
      <AuthedApp />
    </AuthProvider>
  </StrictMode>,
)
