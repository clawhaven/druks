// Harness accent colours, handed out by registry order and rotated, so a
// newly-installed harness gets the next colour with no per-name CSS. First two
// are the existing claude amber / codex violet, so nothing shifts for us.
const HARNESS_PALETTE = ['#f5a85c', '#a78bfa', '#4dd4f4', '#5eead4', '#f472b6', '#a3e635', '#fbbf24', '#60a5fa']

export const harnessColors = (names: string[]): Record<string, string> =>
  Object.fromEntries(names.map((name, i) => [name, HARNESS_PALETTE[i % HARNESS_PALETTE.length]!]))
