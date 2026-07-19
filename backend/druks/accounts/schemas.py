from datetime import datetime

from pydantic import ConfigDict

from druks.schemas import BaseResponse


class AccountResponse(BaseResponse):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str


class PatResponse(BaseResponse):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    token_prefix: str
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
