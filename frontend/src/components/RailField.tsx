import type { ReactNode } from 'react'

/**
 * RailField — a key/value row inside a detail page's rail pane.
 * Wrap several inside ``<div className="wd-fields">…</div>``.
 */
export function RailField({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="wd-field">
      <span className="wd-field-k">{k}</span>
      <span className="wd-field-v">{children}</span>
    </div>
  )
}
