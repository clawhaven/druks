from pydantic import ConfigDict

from druks.schemas import BaseResponse


class SkillResponse(BaseResponse):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    enabled: bool


class CollectionResponse(BaseResponse):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    name: str
    skills: list[SkillResponse]
