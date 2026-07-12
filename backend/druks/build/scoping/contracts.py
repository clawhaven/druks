from typing import Literal

from druks.agents import AgentOutput

from .exceptions import ScoperError


class RelatedRepoOutput(AgentOutput):
    full_name: str
    purpose: str


class SplitTicketOutput(AgentOutput):
    title: str
    problem: str
    scope: str
    acceptance_criteria: list[str]
    blocked_by: list[int]


class SplitProposalOutput(AgentOutput):
    rationale: str
    tickets: list[SplitTicketOutput]


class ScopeBriefOutput(AgentOutput):
    status: Literal["ready", "needs_answers", "split_recommended"]
    problem: str
    scope: str
    acceptance_criteria: list[str]
    stack_hints: list[str]
    related_repos: list[RelatedRepoOutput]
    out_of_scope: list[str]
    # Operator-stated contracts the implementer must honor verbatim — the
    # uncompressed escape hatch the compressed brief loses by design.
    decisions: list[str]
    open_questions: list[str]
    # Always present; non-empty tickets only meaningful when status is
    # split_recommended (empty for the other statuses keeps Codex output flat).
    split_recommendation: SplitProposalOutput

    def to_result(self) -> "ScopeBriefOutput":
        if self.status == "split_recommended" and not self.split_recommendation.tickets:
            raise ScoperError("split_recommended status requires at least one proposed ticket")
        # A child wired to a non-existent sibling (or itself) would silently
        # break dependency rendering later.
        tickets = self.split_recommendation.tickets
        for index, ticket in enumerate(tickets):
            for dep in ticket.blocked_by:
                if dep == index or dep not in range(len(tickets)):
                    raise ScoperError(f"split ticket #{index} has invalid blocked_by index {dep}")
        return self
