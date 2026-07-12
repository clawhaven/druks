import os
from datetime import datetime

from sqlalchemy import Boolean, String, select
from sqlalchemy.orm import Mapped, mapped_column

from druks.core.models import Uuid7Pk
from druks.database import db_session
from druks.extensions.registry import mcp_servers
from druks.mcp.constants import (
    NAME_PATTERN,
    TOKEN_SOURCE_OAUTH,
    TOKEN_SOURCE_STATIC,
    TOKEN_SOURCE_STATIC_FROM_ENV,
    get_bearer_token_env_var,
)
from druks.mcp.exceptions import InvalidServerNameError
from druks.models import Base
from druks.secrets.fields import EncryptedTextField, Secret


class McpServer(Base, Uuid7Pk):
    __tablename__ = "mcp_servers"

    # A row is the operator's overlay: a custom server they added, or a built-in
    # they set state on. Either carries its own url — a built-in overlay copies
    # the url from the built-in def when the operator's choice first creates it.
    name: Mapped[str] = mapped_column(String, unique=True)
    url: Mapped[str] = mapped_column(String)
    token = EncryptedTextField(default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=Base.utc_now)

    @classmethod
    def list_all(cls) -> list["McpServer"]:
        # The raw overlay rows — not the merged registry view (list_resolved).
        return list(db_session().execute(select(cls).order_by(cls.name)).scalars())

    @classmethod
    def get_by_name(cls, name: str) -> "McpServer | None":
        return db_session().execute(select(cls).where(cls.name == name)).scalar_one_or_none()

    @classmethod
    def list_resolved(cls) -> list[dict]:
        # The full view the API reads and delivery resolves from: each built-in
        # definition (url + auth from the registry) overlaid with its operator
        # row's enable choice and secrets, then any fully custom rows. has_token
        # means "can authenticate at delivery", wherever the secret lives — the
        # source var set in druks' env for an env-sourced server, a stored
        # grant for a connected one, the stored token otherwise.
        rows = {server.name: server for server in cls.list_all()}
        servers: list[dict] = []
        for definition in mcp_servers.all():
            row = rows.pop(definition["name"], None)
            token = row.token if row else Secret(b"", "")
            if definition["token_source"] == TOKEN_SOURCE_STATIC_FROM_ENV:
                has_token = bool(os.environ.get(definition["source_env_var"]))
            elif definition["token_source"] == TOKEN_SOURCE_OAUTH:
                has_token = bool(McpOauthGrant.get_by_server(definition["name"]))
            else:
                has_token = bool(token)
            servers.append(
                {
                    "name": definition["name"],
                    "url": definition["url"],
                    "token_source": definition["token_source"],
                    "source_env_var": definition["source_env_var"],
                    "is_enabled": row.is_enabled if row else definition["enabled"],
                    "token": token,
                    "has_token": has_token,
                    "builtin": True,
                }
            )
        for row in rows.values():
            servers.append(
                {
                    "name": row.name,
                    "url": row.url,
                    "token_source": TOKEN_SOURCE_STATIC,
                    "source_env_var": "",
                    "is_enabled": row.is_enabled,
                    "token": row.token,
                    "has_token": bool(row.token),
                    "builtin": False,
                }
            )
        return servers

    @classmethod
    def list_enabled(cls) -> list[dict]:
        # The enabled subset — what a run delivers and the settings UI shows active.
        return [server for server in cls.list_resolved() if server["is_enabled"]]

    @classmethod
    def set_enabled(cls, name: str, is_enabled: bool) -> bool:
        # A built-in has no row until an operator changes its state; the enable
        # choice creates one, carrying the built-in's url. False means the name
        # is neither a row nor a catalog entry.
        server = cls.get_by_name(name)
        if server:
            server.is_enabled = is_enabled
            return True
        if name in mcp_servers:
            cls.create(name=name, url=mcp_servers.get(name)["url"], is_enabled=is_enabled)
            return True
        return False

    @classmethod
    def create(
        cls, *, name: str, url: str, token: str = "", is_enabled: bool = True
    ) -> "McpServer":
        if not NAME_PATTERN.match(name):
            raise InvalidServerNameError(name)
        session = db_session()
        server = cls(name=name, url=url, token=token, is_enabled=is_enabled)
        session.add(server)
        session.flush()
        return server

    def delete(self) -> None:
        session = db_session()
        session.delete(self)
        session.flush()

    @property
    def bearer_token_env_var(self) -> str:
        return get_bearer_token_env_var(self.name)


class McpOauthGrant(Base, Uuid7Pk):
    __tablename__ = "mcp_oauth_grants"

    # One grant per server: the durable outcome of the operator's connect flow —
    # exactly what mint needs to refresh an access token. Connect-time material
    # (authorization endpoint, PKCE verifier, state) is transient and lives in
    # Redis, never here. The refresh token never leaves the backend; the API
    # exposes only that a grant exists.
    server_name: Mapped[str] = mapped_column(String, unique=True)
    # Ciphertext at rest; decrypted only into the refresh request body.
    refresh_token = EncryptedTextField()
    token_endpoint: Mapped[str] = mapped_column(String)
    # The MCP server url the grant is bound to (RFC 8707): an audience-binding
    # authorization server rejects a refresh that doesn't carry the same
    # ``resource`` the code exchange did.
    resource: Mapped[str] = mapped_column(String)
    client_id: Mapped[str] = mapped_column(String)
    # "" for public clients (PKCE-only); some authorization servers issue one
    # even for token_endpoint_auth_method "none" and then expect it on refresh.
    client_secret = EncryptedTextField(default="")
    # When the operator last completed consent. Stamped on every store — the
    # row is upserted on re-connect, so row-creation time would lie.
    connected_at: Mapped[datetime] = mapped_column(default=Base.utc_now)

    @classmethod
    def get_by_server(cls, server_name: str) -> "McpOauthGrant | None":
        return (
            db_session()
            .execute(select(cls).where(cls.server_name == server_name))
            .scalar_one_or_none()
        )

    @classmethod
    def store(
        cls,
        *,
        server_name: str,
        refresh_token: str,
        token_endpoint: str,
        resource: str,
        client_id: str,
        client_secret: str = "",
    ) -> "McpOauthGrant":
        # Connecting again replaces the grant — the recovery path for a revoked
        # or rotten refresh token.
        session = db_session()
        grant = cls.get_by_server(server_name)
        if not grant:
            grant = cls(server_name=server_name)
            session.add(grant)
        grant.refresh_token = refresh_token
        grant.token_endpoint = token_endpoint
        grant.resource = resource
        grant.client_id = client_id
        grant.client_secret = client_secret
        grant.connected_at = cls.utc_now()
        session.flush()
        return grant

    def delete(self) -> None:
        session = db_session()
        session.delete(self)
        session.flush()
