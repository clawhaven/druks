import hashlib
import hmac
from typing import Any, ClassVar

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse, Response

from druks.signals import publish
from druks.webhooks import Webhook


class JiraEvents(Webhook):
    provider = "jira"
    category = "events"

    TOKEN_HEADER: ClassVar[str] = "x-druks-webhook-token"

    def request_is_authentic(self) -> bool:
        # Jira Automation can't HMAC-sign the body, so auth is a shared-secret
        # token header rather than a signature.
        secret = self.settings.jira_webhook_secret
        if not secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jira webhook secret not configured.")
        provided = self.request.headers.get(self.TOKEN_HEADER) or ""
        if not hmac.compare_digest(provided, secret):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Jira webhook token.")
        return True

    def get_action(self) -> str:
        return "issue_event"

    def delivery_key(self) -> str:
        # No delivery id from Automation: key on the issue's change marker +
        # a body digest, so a retry hashes the same and a new transition doesn't.
        issue = self.issue
        updated = str((issue.get("fields") or {}).get("updated") or "")
        digest = hashlib.sha256(self.raw_body).hexdigest()[:16]
        return f"{issue.get('key', '')}:{updated}:{digest}"

    @property
    def issue(self) -> dict[str, Any]:
        # Automation wraps the issue under ``issue``; a bare issue body works too.
        body = self.data if isinstance(self.data, dict) else {}
        nested = body.get("issue")
        return nested if isinstance(nested, dict) else body

    async def on_issue_event(self) -> Response:
        issue = self.issue
        fields = issue.get("fields") or {}
        key = str(issue.get("key") or "")
        if not key:
            self.log_ignored(event="jira", reason="jira_no_issue_key")
            return JSONResponse({"accepted": True})
        assignee = fields.get("assignee") or {}
        status = fields.get("status") or {}
        await publish(
            "ticket.transitioned",
            payload={
                "source": "jira",
                "identifier": key,
                "status": status.get("name") or "",
                "title": str(fields.get("summary") or ""),
                "url": self._issue_url(key),
                "project_name": (fields.get("project") or {}).get("name"),
                "labels": list(fields.get("labels") or []),
                "assignee_email": assignee.get("emailAddress") or None,
                "assignee_name": assignee.get("displayName") or None,
                "completed": False,
                # The "done" status category is Jira's terminal marker — it covers
                # Done/Closed/Won't Do however the workflow names its statuses.
                "terminal": (status.get("statusCategory") or {}).get("key") == "done",
            },
        )
        return JSONResponse({"accepted": True})

    def _issue_url(self, key: str) -> str | None:
        base = self.settings.jira_base_url
        return f"{base.rstrip('/')}/browse/{key}" if base and key else None
