from datetime import datetime

from pydantic import ConfigDict, Field

from druks.schemas import BaseResponse


class AccountResponse(BaseResponse):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str


class PatResponse(BaseResponse):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    # Wire name is the spec's `prefix`; the column keeps its qualified name.
    prefix: str = Field(validation_alias="token_prefix")
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_active: bool
    is_expired: bool
    is_revoked: bool


class CreatedPatResponse(PatResponse):
    # The plaintext, returned exactly once at create — never stored or listed.
    token: str
