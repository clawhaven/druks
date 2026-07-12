import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import { absTime, absTimeCompact } from './format'

interface PreferencesContextValue {
  timezone: string
  isLoaded: boolean
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null)

// Default fallback when settings haven't loaded yet or the API call
// failed. We intentionally do NOT sniff the browser timezone — the
// operator-facing setting in Settings → Preferences is the single
// source of truth, and an implicit browser-sniff would silently
// disagree with what the server thinks the timezone is on every
// other render surface (PR comments, logs, etc., all UTC by default).
const _FALLBACK_TIMEZONE = 'UTC'

export function UserPreferencesProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    staleTime: 60_000,
  })

  const value = useMemo<PreferencesContextValue>(() => {
    const saved = query.data?.timezone
    return {
      timezone: saved || _FALLBACK_TIMEZONE,
      isLoaded: query.isSuccess,
    }
  }, [query.data?.timezone, query.isSuccess])

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- hook co-located with its context
export function useTimezone(): string {
  const ctx = useContext(PreferencesContext)
  return ctx?.timezone ?? _FALLBACK_TIMEZONE
}

/**
 * Returns the time-formatting helpers pre-bound to the operator's active
 * timezone. Call sites that previously imported ``absTime`` / ``absTimeCompact``
 * from ``lib/format`` should switch to this hook so the user's preference
 * applies uniformly.
 */
// eslint-disable-next-line react-refresh/only-export-components -- hook co-located with its context
export function useFormatters() {
  const timezone = useTimezone()
  return useMemo(
    () => ({
      timezone,
      absTime: (iso: string) => absTime(iso, timezone),
      absTimeCompact: (iso: string) => absTimeCompact(iso, timezone),
    }),
    [timezone],
  )
}
