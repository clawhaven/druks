import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { App } from '../App'
import { UserPreferencesProvider } from '../lib/preferences'

// Everything that queries the API lives BELOW the auth gate, with a query
// cache scoped to this mount — the AuthProvider unmounts it on logout/expiry,
// so nothing cached for one account can render for the next, and no query
// fires before a session exists.
export function AuthedApp() {
  const [queryClient] = useState(
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
  )
  return (
    <QueryClientProvider client={queryClient}>
      <UserPreferencesProvider>
        <App />
      </UserPreferencesProvider>
    </QueryClientProvider>
  )
}
