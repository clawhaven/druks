from druks.build.contracts import PlanData, PlanReview, Question, QuestionOption
from druks.build.enums import ReviewDecision
from druks.build.policy import RepoPolicy
from druks.build.workflows import Build, BuildWorkflow


async def test_plan_phase_threads_free_text_into_the_next_pass(monkeypatch):
    """A free-text answer and a request_changes note both reach the next plan pass
    (answered_questions / operator_note) — a re-plan is never blind."""
    flow = BuildWorkflow()
    flow._policy = RepoPolicy()  # plan_approval defaults to the human gate
    flow._settings = BuildWorkflow.Settings()

    plans = iter(
        [
            PlanData(
                plan_markdown="v1",
                questions=[
                    Question(
                        id="q1",
                        prompt="Which cache?",
                        options=[QuestionOption(id="a", label="Redis")],
                    )
                ],
            ),
            PlanData(plan_markdown="v2"),
            PlanData(plan_markdown="v3"),
        ]
    )
    passes: list[dict] = []

    async def fake_plan_agent():
        # What the planner's template reads on each pass.
        passes.append({"answered": flow.answered_questions, "note": flow.operator_note})
        return next(plans)

    async def fake_review_agent():
        return PlanReview(decision=ReviewDecision.REQUEST_CHANGES)

    monkeypatch.setattr(Build, "generate_plan", fake_plan_agent)
    monkeypatch.setattr(Build, "review_plan", fake_review_agent)

    replies = iter(
        [
            {
                "action": "request_changes",
                "answers": {"q1": "memcache — redis is banned here"},
                "note": "",
            },
            {"action": "request_changes", "answers": {}, "note": "add a rollback section"},
            {"action": "approve", "answers": {}, "note": ""},
        ]
    )

    async def fake_review(*, questions=None):
        return next(replies)

    flow.review = fake_review

    assert await flow._plan_phase() is True
    assert passes == [
        {"answered": [], "note": ""},
        {
            "answered": [{"question": "Which cache?", "answer": "memcache — redis is banned here"}],
            "note": "",
        },
        {"answered": [], "note": "add a rollback section"},
    ]
