from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from bigrag.db.models import ConnectorSource, ConnectorSourceCredential


async def upsert_source_credential(
    session: Any,
    *,
    source: ConnectorSource,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    session_token: str | None = None,
    session_token_set: bool = False,
    region: str,
    endpoint_url: str | None,
    force_path_style: bool,
) -> ConnectorSourceCredential:
    credential = await session.scalar(
        sa.select(ConnectorSourceCredential).where(ConnectorSourceCredential.source_id == source.id)
    )
    if credential is None:
        if not access_key_id or not secret_access_key:
            raise ValueError("S3 access key ID and secret access key are required")
        credential = ConnectorSourceCredential(
            source_id=source.id,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            region=region,
            endpoint_url=endpoint_url,
            force_path_style=force_path_style,
        )
        session.add(credential)
        return credential
    if access_key_id is not None or secret_access_key is not None:
        if not access_key_id or not secret_access_key:
            raise ValueError("S3 access key ID and secret access key must be rotated together")
        credential.access_key_id = access_key_id
        credential.secret_access_key = secret_access_key
        credential.session_token = session_token
    elif session_token_set:
        credential.session_token = session_token
    credential.region = region
    credential.endpoint_url = endpoint_url
    credential.force_path_style = force_path_style
    return credential
