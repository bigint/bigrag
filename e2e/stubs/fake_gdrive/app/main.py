from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .files import FAKE_FILES, file_body, file_metadata, list_files

app = FastAPI(title="fake-gdrive", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/o/oauth2/auth", response_class=HTMLResponse)
async def oauth_consent(
    client_id: str = Query(default=""),
    redirect_uri: str = Query(default=""),
    state: str = Query(default=""),
    scope: str = Query(default=""),
    response_type: str = Query(default="code"),
) -> HTMLResponse:
    target = f"{redirect_uri}?code=fake-auth-code&state={state}"
    body = (
        "<!doctype html><html><body>"
        "<h1>Mock Google consent</h1>"
        f"<p>client_id={client_id} scope={scope}</p>"
        f"<a id='grant' href='{target}'>Grant access</a>"
        "</body></html>"
    )
    return HTMLResponse(content=body)


@app.post("/token")
async def oauth_token(
    grant_type: str = Form(default=""),
    code: str = Form(default=""),
    client_id: str = Form(default=""),
    client_secret: str = Form(default=""),
    redirect_uri: str = Form(default=""),
    refresh_token: str = Form(default=""),
    scope: str = Form(default=""),
) -> dict[str, Any]:
    if grant_type == "authorization_code" and code != "fake-auth-code":
        raise HTTPException(status_code=400, detail="invalid_grant")
    return {
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": scope or "https://www.googleapis.com/auth/drive.readonly",
    }


@app.get("/drive/v3/about")
async def drive_about(fields: str = Query(default="")) -> dict[str, Any]:
    return {
        "user": {
            "emailAddress": "e2e-user@example.com",
            "displayName": "E2E User",
        }
    }


@app.get("/drive/v3/files")
async def drive_files(
    q: str | None = Query(default=None),
    pageSize: int = Query(default=100),
    fields: str | None = Query(default=None),
    pageToken: str | None = Query(default=None),
) -> dict[str, Any]:
    items = list_files()
    if q:
        ql = q.lower()
        items = [f for f in items if ql in (f.get("name") or "").lower()]
    return {"files": items[:pageSize], "incompleteSearch": False}


@app.get("/drive/v3/files/{file_id}")
async def drive_file(
    file_id: str,
    alt: str | None = Query(default=None),
    fields: str | None = Query(default=None),
):
    meta = file_metadata(file_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    if alt == "media":
        body = file_body(file_id)
        if body is None:
            raise HTTPException(status_code=400, detail="not_a_binary_file")
        return Response(content=body, media_type=meta.get("mimeType") or "application/octet-stream")
    return JSONResponse(content=meta)


@app.get("/drive/v3/files/{file_id}/export")
async def drive_export(file_id: str, mimeType: str = Query(default="text/plain")):
    if file_id not in FAKE_FILES:
        raise HTTPException(status_code=404, detail="file_not_found")
    body = file_body(file_id)
    if body is None:
        raise HTTPException(status_code=400, detail="not_exportable")
    return Response(content=body, media_type=mimeType)
