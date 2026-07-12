import { useEffect } from 'react'
import { useLocation } from 'wouter'

/**
 * Replace the current URL with ``canonical`` if they differ. Used by
 * detail pages once they've loaded enough data to compute their
 * canonical ``/<type>/<id>-<slug>`` form. Pass ``null`` while the data
 * is still loading — the hook is a no-op until you have something to
 * navigate to.
 *
 * ``replace: true`` so the user's back button doesn't get a duplicate
 * non-canonical history entry.
 */
export function useCanonicalPath(canonical: string | null | undefined): void {
  const [location, navigate] = useLocation()
  useEffect(() => {
    if (!canonical) return
    if (location !== canonical) {
      navigate(canonical, { replace: true })
    }
  }, [location, canonical, navigate])
}
