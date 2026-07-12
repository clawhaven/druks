import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'

import { EmptyState } from './EmptyState'

/**
 * queryGate — returns an EmptyState while a useQuery is loading or errored,
 * otherwise null. Call it at the top of a page render and short-circuit:
 *
 *     const gate = queryGate(query, { loadingMsg: 'loading watch',
 *                                     errorMsg: 'could not load watch' })
 *     if (gate) return <Page ...>{gate}</Page>
 *     const data = query.data!
 *     ...
 */
interface QueryGateOpts {
  loadingMsg?: string
  errorMsg?: string
  errorSub?: string
}

export function queryGate<T>(
  query: UseQueryResult<T>,
  opts: QueryGateOpts = {},
): ReactNode | null {
  if (query.isLoading) return <EmptyState glyph="…" msg={opts.loadingMsg ?? 'loading'} />
  if (query.isError || query.data === undefined) {
    return <EmptyState glyph="!" msg={opts.errorMsg ?? 'could not load'} sub={opts.errorSub} />
  }
  return null
}
