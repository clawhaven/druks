interface Props {
  glyph?: string
  msg?: string
  sub?: string
  action?: React.ReactNode
}

export function EmptyState({ glyph, msg, sub, action }: Props) {
  return (
    <div className="empty-state panel-empty">
      {glyph && <div className="empty-glyph">{glyph}</div>}
      {msg && <div className="empty-msg">{msg}</div>}
      {sub && <div className="empty-sub mono dim">{sub}</div>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  )
}
