interface Props {
  prNumber?: number | null
  prUrl?: string | null
}

/**
 * Compact PR cell: just ``#N`` (a link when ``prUrl`` is set) or an em-dash
 * when there's no PR yet. Used by the dashboard's active + finished tables.
 * The richer ``RepoPRCell`` variant covers the places that genuinely want
 * the repo string rendered (e.g. when no project column is present).
 */
export function PRCell({ prNumber, prUrl }: Props) {
  if (prNumber == null) return <span className="dim">—</span>
  return (
    <span className="row-pr-cell mono dim">
      <a
        className="row-pr-num"
        href={prUrl ?? '#'}
        target={prUrl ? '_blank' : undefined}
        rel="noreferrer"
        onClick={(event) => event.stopPropagation()}
      >
        #{prNumber}
      </a>
    </span>
  )
}
