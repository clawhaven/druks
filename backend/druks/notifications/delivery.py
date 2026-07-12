import apprise
import httpx

from druks.notifications.buttons import encode_button
from druks.notifications.exceptions import DeliveryError, DisabledDestinationError
from druks.notifications.models import Destination, DestinationKind

_SEND_TIMEOUT_SECONDS = 10.0


async def deliver(
    destination: Destination,
    body: str,
    *,
    actions: list[dict] | None = None,
    token: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    # idempotency_key is part of the seam for providers that dedup on it (the
    # outbox passes the notification id); Slack webhooks and Apprise ignore it.
    if not destination.is_enabled:
        raise DisabledDestinationError(destination.name)
    url = destination.url  # the one place the secret is read in the clear
    if destination.kind == DestinationKind.SLACK_WEBHOOK and actions:
        # Interactivity has no cross-provider abstraction (Apprise can't
        # express buttons), so the actionable path is hand-rolled Block Kit.
        await _post_slack_blocks(destination.name, url, body, actions, token)
        return
    await _notify_apprise(destination.name, url, body)


async def _post_slack_blocks(
    name: str, url: str, body: str, actions: list[dict], token: str | None
) -> None:
    message = {
        "text": body,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": body}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": action["label"]},
                        "action_id": encode_button(token, action["id"]),
                    }
                    for action in actions
                ],
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=message)
        response.raise_for_status()
    except httpx.HTTPError as error:
        # from None: httpx error text embeds the webhook URL (the credential),
        # so the chain must not survive into logs; the class name is enough.
        raise DeliveryError(name, type(error).__name__) from None


async def _notify_apprise(name: str, url: str, body: str) -> None:
    # The URL was already parse-checked at save; a stored one that no longer
    # parses leaves zero servers and notify returns falsy — caught below.
    sender = apprise.Apprise()
    sender.add(url)
    try:
        sent = await sender.async_notify(body=body)
    except Exception as error:
        # from None: provider exceptions can embed the webhook URL.
        raise DeliveryError(name, type(error).__name__) from None
    if not sent:
        raise DeliveryError(name, "the provider rejected the notification")
