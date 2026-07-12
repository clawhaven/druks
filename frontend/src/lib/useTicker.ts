import { useEffect, useState } from 'react'

/**
 * Bumps a counter every second so any component using ``tick`` re-renders.
 * Used by elapsed-time displays that need to climb in real time. Pass
 * ``active=false`` to disable the timer when there's nothing to animate.
 */
export function useTicker(active = true): number {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!active) return undefined
    const id = window.setInterval(() => setTick((t) => t + 1), 1000)
    return () => window.clearInterval(id)
  }, [active])
  return tick
}
