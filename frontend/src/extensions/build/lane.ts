import type { SubjectStatus } from '../../api/types'

// Build's lane copy, composed from the platform's status facts — the backend
// ships data; the extension owns its own vocabulary.

function kindLabel(kind: string): string {
  const tail = kind.split('.').pop() ?? kind
  const spaced = tail.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export function laneLabel(status: SubjectStatus): string {
  if (status.state === 'pending_input') return status.askLabel || 'Waiting on you'
  if (status.state === 'running' || status.state === 'scheduled') {
    return kindLabel(status.agent ?? status.kind ?? '')
  }
  if (status.state === 'failed' && status.reason === 'gate_timeout' && status.kind) {
    // An unanswered gate, not a crash — the run is terminal, so a fresh
    // trigger goes straight through; say so instead of a bare "failed".
    return `${kindLabel(status.kind)} timed out — re-trigger to retry`
  }
  return ''
}
