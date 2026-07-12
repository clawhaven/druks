import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from druks.build import workflows as build_workflows
from druks.prompts import render_prompt

_OP_TEMPLATES = [
    "generate_plan.md",
    "review_plan.md",
    "revise_contract.md",
    "implement.md",
    "evaluate_implementation.md",
    "review_code.md",
    "triage_human_feedback.md",
]


def _workflow() -> SimpleNamespace:
    """A stand-in BuildWorkflow exposing the attributes the templates read."""
    input = SimpleNamespace(
        repo="acme/widget",
        issue_number=None,
        ticket_ref="ACME-1",
        task_owner_name=None,
        task_owner_email=None,
    )
    return SimpleNamespace(
        input=input,
        branch="agent/eng-1",
        pr_number=7,
        plan_revision=1,
        implementation_revision=0,
        finalized_base_sha=None,
        finalized_pr_sha=None,
        current_plan=None,
        acceptance_criteria=[],
        reviewer_requirements=[],
        implementation_reviews=[],
        human_feedback=[],
        related_repos=[],
        answered_questions=[],
        operator_note="",
    )


@pytest.mark.parametrize("template", _OP_TEMPLATES)
async def test_build_operation_prompt_renders(template):
    output = await render_prompt(
        f"build/build_workflow/{template}",
        repo="acme/widget",
        workflow=_workflow(),
        verification="VERIFICATION-BLOCK",
        workspace=SimpleNamespace(
            repo_path="/home/agent/work/repo",
            workspace_root="/home/agent/work",
        ),
    )

    # The workflow-derived bits resolved — a leftover ``operation`` ref would
    # have raised on StrictUndefined.
    assert "acme/widget" in output


async def test_implement_prompt_provisions_when_no_pr_exists():
    # The first delivery has no PR: the implementer is told to create the branch and
    # open the draft PR; the revision path (dismiss stale reviews) must not render.
    workflow = _workflow()
    workflow.branch = None
    workflow.pr_number = None
    output = await render_prompt(
        "build/build_workflow/implement.md",
        repo="acme/widget",
        workflow=workflow,
        verification="VERIFICATION-BLOCK",
        workspace=SimpleNamespace(
            repo_path="/home/agent/work/repo",
            workspace_root="/home/agent/work",
        ),
    )
    assert "gh pr create --draft" in output
    # The PR body carries the plan — what reviewers review the diff against.
    assert "## Plan" in output
    assert "dismiss the PR's existing reviews" not in output


async def test_generate_plan_prompt_quotes_operator_content():
    """Free-text answers and the operator's note render block-quoted line by line —
    operator words stay answer content in the prompt, never instruction text."""
    workflow = _workflow()
    workflow.answered_questions = [{"question": "Which cache?", "answer": "redis\nwith a 5m TTL"}]
    workflow.operator_note = "Tighten the rollout.\nSplit phase 2."
    output = await render_prompt(
        "build/build_workflow/generate_plan.md",
        repo="acme/widget",
        workflow=workflow,
        verification="VERIFICATION-BLOCK",
        workspace=SimpleNamespace(
            repo_path="/home/agent/work/repo",
            workspace_root="/home/agent/work",
        ),
    )
    assert "> redis\n  > with a 5m TTL" in output
    assert "> Tighten the rollout.\n> Split phase 2." in output


@pytest.mark.parametrize("template", _OP_TEMPLATES)
async def test_build_prompt_orders_the_ticket_fetch(template):
    """Every build agent is ordered to fetch the ticket from its source before
    acting — a mandatory first step, not a suggestion. Regression guard for the
    silently-skipped-fetch bug (agents working off the ticket ref alone)."""
    workflow = _workflow()
    workflow.input.source = "linear"
    output = await render_prompt(
        f"build/build_workflow/{template}",
        repo="acme/widget",
        workflow=workflow,
        verification="VERIFICATION-BLOCK",
        workspace=SimpleNamespace(
            repo_path="/home/agent/work/repo",
            workspace_root="/home/agent/work",
        ),
    )
    assert "MANDATORY FIRST ACTION" in output
    assert "fetch `ACME-1`" in output
    assert "from Linear" in output


async def test_review_code_prompt_owns_its_followup_subissue():
    """The reviewer files its own follow-up sub-issue via its tracker tools —
    regression guard for the dangling promise left when druks-side sub-issue
    creation was removed and nothing filed it. LLM-first: the agent does the
    tracker write, druks acts on nothing it returns."""
    workflow = _workflow()
    workflow.input.source = "linear"
    output = await render_prompt(
        "build/build_workflow/review_code.md",
        repo="acme/widget",
        workflow=workflow,
        verification="VERIFICATION-BLOCK",
        workspace=SimpleNamespace(
            repo_path="/home/agent/work/repo",
            workspace_root="/home/agent/work",
        ),
    )
    assert "File a follow-up sub-issue" in output
    assert "same tracker tools" in output  # the agent writes it, not druks
    assert '"summary"' in output  # the only thing it returns


def test_build_workflow_exposes_template_attrs(db_session):
    # Every build prompt reads workflow.<attr> off the real BuildWorkflow; the
    # _workflow() stand-in above can't catch an attr the real class dropped, so
    # assert the class satisfies the contract across *all* of its templates.

    prompts_root = Path(build_workflows.__file__).resolve().parents[2]
    prompts_dir = prompts_root / "templates/prompts/build/build_workflow"
    attrs: set[str] = set()
    for template in prompts_dir.glob("*.md"):
        attrs |= set(re.findall(r"workflow\.([a-z_]+)", template.read_text()))
    workflow = build_workflows.BuildWorkflow()  # input/state are instance attrs
    workflow.input = build_workflows.BuildWorkflow._run_input_model(repo="acme/widget")
    missing = sorted(a for a in attrs if not hasattr(workflow, a))
    assert not missing, f"BuildWorkflow missing template attrs: {missing}"
