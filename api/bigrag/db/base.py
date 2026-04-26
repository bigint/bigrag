"""Declarative base and reusable column type annotations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSONB, list: JSONB}


UUIDpk = Annotated[
    UUID,
    mapped_column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
]
TS = Annotated[
    datetime,
    mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
]
TSupd = Annotated[
    datetime,
    mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    ),
]
