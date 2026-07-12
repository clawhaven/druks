interface Props {
  ticketRef?: string | null
  ticketUrl?: string | null
  fallback: string
}

/**
 * Ticket cell: the ticket ref (e.g. ``ACME-398``) rendered as a link to
 * Linear when ``ticketUrl`` is set, otherwise plain text. Falls back to
 * ``fallback`` (e.g. ``#<id>``) when there's no ref at all.
 *
 * Mirrors ``PRCell``: the anchor stops row-click propagation so clicking
 * the ticket opens Linear instead of triggering the row's navigate-into
 * handler.
 */
export function TicketCell({ ticketRef, ticketUrl, fallback }: Props) {
  if (ticketRef && ticketUrl) {
    return (
      <span className="row-id mono">
        <a
          className="row-ticket-link"
          href={ticketUrl}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
        >
          {ticketRef}
        </a>
      </span>
    )
  }
  return <span className="row-id mono">{ticketRef ?? fallback}</span>
}
