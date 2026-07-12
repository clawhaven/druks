import type { ReactNode } from 'react'

/**
 * PageHeader — the eyebrow + count + meta + right-slot band used at the
 * top of every list page (events, history, work items, signals,
 * watches, research). Drop into <Page header={...}>.
 */
interface PageHeaderProps {
  eyebrow: ReactNode
  count?: number
  meta?: ReactNode
  /** Right slot — the page wraps it however it needs (filters row,
   * live indicator, action buttons). */
  right?: ReactNode
}

export function PageHeader({ eyebrow, count, meta, right }: PageHeaderProps) {
  return (
    <div className="active-page-head">
      <div className="active-page-title">
        <h1 className="dash-h1-main">
          <span className="dash-h1-eyebrow">{eyebrow}</span>
          {count !== undefined && <span className="dash-h1-count">({count})</span>}
        </h1>
        {meta && <div className="active-page-meta mono dim">{meta}</div>}
      </div>
      {right}
    </div>
  )
}
