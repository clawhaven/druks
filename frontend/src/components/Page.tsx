import type { ReactNode } from 'react'

/**
 * Page — the shell every route renders its content inside.
 *
 * - ``scroll="page"`` (default): the page-shell itself scrolls; the
 *   whole page scrolls as a unit. Use ``position: sticky`` on a child
 *   if you want it pinned.
 * - ``scroll="internal"``: header is pinned outside the scrolling body;
 *   ``children`` scroll independently. Use for filters above a list or
 *   multi-pane cockpits.
 *
 * The ``header`` slot is non-shrinking in both apps (rides along with
 * the body in ``scroll="page"``, stays pinned in ``scroll="internal"``).
 */
interface PageProps {
  children: ReactNode
  /** Page-specific styling (max-width, background, padding). Don't
   * override flex / overflow / min-height — .page-shell owns those. */
  className?: string
  header?: ReactNode
  scroll?: 'page' | 'internal'
}

export function Page({ children, className, header, scroll = 'page' }: PageProps) {
  const cls = ['page-shell', className].filter(Boolean).join(' ')
  return (
    <div className={cls} data-scroll={scroll}>
      {header !== undefined && <div className="page-shell-header">{header}</div>}
      <div className="page-shell-body">{children}</div>
    </div>
  )
}
