import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { App } from './App'
import { UserPreferencesProvider } from './lib/preferences'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // SSE delivers freshness; snapshots are explicit refetches.
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
})

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element #root not found')

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <UserPreferencesProvider>
        <App />
      </UserPreferencesProvider>
    </QueryClientProvider>
  </StrictMode>,
)
