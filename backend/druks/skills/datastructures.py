from typing import NamedTuple


class InstalledSkill(NamedTuple):
    name: str
    description: str
    path: str
    content_hash: str


class CollectionContents(NamedTuple):
    name: str
    skills: list[InstalledSkill]
