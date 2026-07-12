import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type {
  UsageHistoryResponse,
  UsageResponse,
  UsageTodayResponse,
} from '../api/types'

/**
 * Read the latest cached usage snapshot.
 *
 * The backend's poller writes a snapshot every ~5 min; this hook just
 * re-reads at a 60s cadence (+ on window focus) so a pill update is
 * visible within a minute of the snapshot landing. The actual scrape
 * runs server-side — this hook never triggers one. To force a scrape,
 * call ``refresh()`` which POSTs ``/api/usage/refresh``.
 *
 * Returns the raw query state alongside a ``refresh()`` helper. The
 * helper enqueues the scrape and then nudges the query to refetch a
 * couple of times so the new row appears without waiting for the
 * background poll.
 */
export function useUsage() {
  const queryClient = useQueryClient()
  const query = useQuery<UsageResponse>({
    queryKey: ['usage'],
    queryFn: () => api.usage(),
    // Stale at 30s so a manual refresh shows up promptly when the user
    // pops back; full refetch interval is 60s for the always-visible
    // pill. Both are inexpensive (one row each per CLI).
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    // 5xx during a worker restart is transient; one retry covers it.
    retry: 1,
  })

  async function refresh() {
    await api.refreshUsage()
    // Poll twice — scraper usually finishes in <5s, so 2× 3s = 6s
    // window covers it without spamming the API. The background
    // refetchInterval handles the case where the scrape took longer.
    for (let i = 0; i < 2; i++) {
      await new Promise((r) => setTimeout(r, 3000))
      const fresh = await queryClient.fetchQuery({
        queryKey: ['usage'],
        queryFn: () => api.usage(),
      })
      if (fresh.harnesses.some((h) => h.ageSeconds !== null && h.ageSeconds < 10)) break
    }
  }

  return { ...query, refresh }
}

/**
 * Scrape history for the usage page's trend sparklines + burn-rate
 * math. New points only land when the poller writes a snapshot
 * (~5 min), so a 60s refetch mirrors :func:`useUsage` without extra
 * server work — the endpoint reads rows already in SQLite.
 */
export function useUsageHistory() {
  return useQuery<UsageHistoryResponse>({
    queryKey: ['usage-history'],
    queryFn: () => api.usageHistory(),
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    retry: 1,
  })
}

/**
 * Today's spend/tokens split by provider (same day boundary as the
 * sys-strip's spend-today figure). Aggregated from druks' own run
 * records, so it moves when runs finish — not on the scrape cadence.
 */
export function useUsageToday() {
  return useQuery<UsageTodayResponse>({
    queryKey: ['usage-today'],
    queryFn: () => api.usageToday(),
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    retry: 1,
  })
}
