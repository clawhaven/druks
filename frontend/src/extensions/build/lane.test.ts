import { describe, expect, it } from 'vitest'

import type { SubjectStatus } from '../../api/types'
import { laneLabel } from './lane'

function status(overrides: Partial<SubjectStatus>): SubjectStatus {
  return {
    state: 'running',
    kind: 'build.scope',
    agent: null,
    askLabel: null,
    failure: null,
    reason: null,
    ...overrides,
  }
}

describe('laneLabel', () => {
  it('parked shows the declared ask', () => {
    expect(laneLabel(status({ state: 'pending_input', askLabel: 'Approve the plan' }))).toBe(
      'Approve the plan',
    )
  })

  it('parked without an ask label falls back', () => {
    expect(laneLabel(status({ state: 'pending_input' }))).toBe('Waiting on you')
  })

  it('running shows the live agent over the kind', () => {
    expect(laneLabel(status({ agent: 'implement' }))).toBe('Implement')
  })

  it('running before any call shows the kind', () => {
    expect(laneLabel(status({}))).toBe('Scope')
  })

  it('a timed-out gate renders the re-trigger hint', () => {
    expect(laneLabel(status({ state: 'failed', reason: 'gate_timeout' }))).toBe(
      'Scope timed out — re-trigger to retry',
    )
  })

  it('a crash renders no line', () => {
    expect(laneLabel(status({ state: 'failed', failure: 'boom' }))).toBe('')
  })

  it('the hint is failed-only — an orphaned run with the code renders nothing', () => {
    expect(laneLabel(status({ state: 'orphaned', reason: 'gate_timeout' }))).toBe('')
  })
})
