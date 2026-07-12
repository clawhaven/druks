from druks.agents import AgentOutput


class NoteSummary(AgentOutput):
    # What the summarizer agent returns: a one-line distillation of the note it read.
    summary: str
