interface Props {
  repoBare?: string | null
  project?: string | null
}

/**
 * Repo column — bare repo name as plain text, with the Druks Project as a
 * hover tooltip when bound. Items without a repo (e.g. scope rows pre-target)
 * render an em-dash.
 */
export function RepoCell({ repoBare, project }: Props) {
  if (!repoBare) return <span className="mono dim">—</span>
  const title = project ? `${project} · ${repoBare}` : repoBare
  return (
    <span className="row-repo mono" title={title}>
      {repoBare}
    </span>
  )
}
