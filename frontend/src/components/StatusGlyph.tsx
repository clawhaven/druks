import { STATES } from '../lib/states'
import type { RunState } from '../api/types'

interface Props {
  state: RunState
  pulse?: boolean
  size?: number
}

export function StatusGlyph({ state, pulse = false, size = 10 }: Props) {
  const style = STATES[state]
  return (
    <span
      className={`glyph${pulse ? ' glyph-pulse' : ''}`}
      style={{ color: style.color, fontSize: `${size}px` }}
      title={style.label}
    >
      {style.glyph}
    </span>
  )
}
