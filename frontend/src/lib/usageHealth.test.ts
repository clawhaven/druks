import { expect, test } from 'vitest'

import { usageTone } from './usageHealth'

// Boundaries are the whole point — pill and panel now share this one ladder,
// so a drift here recolours both surfaces at once.
test('usageTone ladder: crit <=15, warn <=40, ok above', () => {
  expect(usageTone(0)).toBe('crit')
  expect(usageTone(15)).toBe('crit')
  expect(usageTone(16)).toBe('warn')
  expect(usageTone(37)).toBe('warn') // the flagged case: same tone in pill + card
  expect(usageTone(40)).toBe('warn')
  expect(usageTone(41)).toBe('ok')
  expect(usageTone(100)).toBe('ok')
})
