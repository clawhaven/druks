from datetime import datetime

from druks.workflows import SubjectSummary

from druks_field_notes.models import Note


class NoteView(SubjectSummary):
    # The note's domain header — what only field_notes knows. The platform's subject
    # read-side composes it with the generic status + timeline; ``id`` is the subject key.
    body: str
    summary: str | None = None
    created_at: datetime

    @classmethod
    def from_note(cls, note: Note) -> "NoteView":
        return cls(
            id=str(note.id),
            body=note.body,
            summary=note.summary,
            created_at=note.created_at,
        )
