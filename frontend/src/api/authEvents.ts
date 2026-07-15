// One tiny pub/sub for "the session is gone": the API client and the SSE hook
// emit it on a 401, the AuthProvider subscribes and unmounts the app (which
// closes every stream). Module-local so client.ts and AuthProvider don't
// import each other.

type Listener = () => void

const listeners = new Set<Listener>()

export function onAuthExpired(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function emitAuthExpired(): void {
  for (const listener of listeners) listener()
}
