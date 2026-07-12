import { useEffect, useState } from 'react'

/**
 * useFlashNote — a piece of state that auto-clears after a timeout.
 *
 * Pages that show a brief "✓ saved" / "⊘ dismissed" toast after a
 * mutation and clear it after a few seconds. This hook is that pattern.
 *
 *     const [note, setNote] = useFlashNote<string>()
 *     // ... setNote('✓ saved') inside a mutation handler
 *     // ... {note && <div className="toast">{note}</div>}
 */
export function useFlashNote<T>(timeoutMs = 3000) {
  const [note, setNote] = useState<T | null>(null)
  useEffect(() => {
    if (!note) return
    const id = window.setTimeout(() => setNote(null), timeoutMs)
    return () => window.clearTimeout(id)
  }, [note, timeoutMs])
  return [note, setNote] as const
}
