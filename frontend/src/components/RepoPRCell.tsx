interface Props {
  repo?: string | null
  prNumber?: number | null
  prUrl?: string | null
}

export function RepoPRCell({ repo, prNumber, prUrl }: Props) {
  if (!repo && prNumber == null) return <span className="dim">—</span>
  return (
    <span className="repo-pr mono dim">
      {repo}
      {prNumber != null && (
        <a
          className="repo-pr-pr"
          href={prUrl ?? '#'}
          target={prUrl ? '_blank' : undefined}
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
        >
          #{prNumber}
        </a>
      )}
    </span>
  )
}
