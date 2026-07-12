from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.engine import Engine

from druks.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


SettingsDep = Annotated[Settings, Depends(get_settings)]
EngineDep = Annotated[Engine, Depends(get_engine)]
