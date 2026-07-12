import logging
from typing import ClassVar

from fastapi.responses import JSONResponse, Response

from druks.core.apis.linear import compute_delivery_key
from druks.signals import publish
from druks.webhooks import Webhook, verify_hmac_sha256

logger = logging.getLogger(__name__)


class LinearEvents(Webhook):
    provider = "linear"
    category = "events"

    SIGNATURE_HEADER: ClassVar[str] = "linear-signature"

    def request_is_authentic(self) -> bool:
        verify_hmac_sha256(
            self.raw_body,
            self.request.headers.get(self.SIGNATURE_HEADER),
            self.settings.linear_webhook_secret,
            prefix="",
        )
        return True

    def delivery_key(self) -> str:
        headers = {k.lower(): v for k, v in self.request.headers.items()}
        return compute_delivery_key(headers, self.raw_body, self.data)

    def get_action(self) -> str:
        action = self.data.get("action")
        if self.data.get("type") == "Comment" and action == "create":
            return "comment_created"
        if action == "update" and "stateId" in (self.data.get("updatedFrom") or {}):
            return "state_transition"
        return "ticket_change"

    async def on_state_transition(self) -> Response:
        issue = self.data["data"]
        state = issue.get("state") or {}
        project = issue.get("project") or {}
        assignee = issue.get("assignee") or {}
        identifier = issue["identifier"]
        await publish(
            "ticket.transitioned",
            payload={
                "source": "linear",
                "identifier": identifier,
                "status": state.get("name", ""),
                "title": str(issue.get("title") or ""),
                "url": str(issue.get("url") or "") or None,
                "project_name": project.get("name"),
                "labels": [],
                "assignee_email": assignee.get("email") or None,
                "assignee_name": assignee.get("name") or None,
                "completed": state.get("type") == "completed",
                # State types are Linear's fixed vocabulary — terminal-ness can't
                # be read off status names, which every team customizes.
                "terminal": state.get("type") in ("completed", "canceled"),
            },
        )
        return _accepted()

    async def on_comment_created(self) -> Response:
        comment = self.data["data"]
        await publish(
            "ticket.commented",
            payload={
                "source": "linear",
                "parent_id": comment.get("parentId"),
                "issue_id": comment.get("issueId"),
            },
        )
        return _accepted()


def _accepted() -> Response:
    return JSONResponse({"accepted": True})
