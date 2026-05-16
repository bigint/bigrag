from __future__ import annotations

FAKE_FILES: dict[str, dict] = {
    "doc-1": {
        "id": "doc-1",
        "name": "Acme Onboarding.gdoc",
        "mimeType": "application/vnd.google-apps.document",
        "modifiedTime": "2026-05-01T10:00:00.000Z",
        "size": "2048",
        "parents": ["root"],
        "body": (
            "# Acme Onboarding\n\n"
            "Welcome to Acme Corp. Our mission is to ship reliable RAG "
            "infrastructure to the open-source community. The current "
            "engineering team has 12 members across three time zones."
        ),
    },
    "sheet-1": {
        "id": "sheet-1",
        "name": "Q1 Roadmap.gsheet",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "modifiedTime": "2026-04-15T09:30:00.000Z",
        "size": "4096",
        "parents": ["root"],
        "body": (
            "milestone,owner,status\n"
            "fake-openai stub,e2e,done\n"
            "fake-gdrive stub,e2e,done\n"
            "webhook-sink stub,e2e,done\n"
        ),
    },
    "pdf-1": {
        "id": "pdf-1",
        "name": "Architecture.pdf",
        "mimeType": "application/pdf",
        "modifiedTime": "2026-03-20T14:00:00.000Z",
        "size": "8192",
        "parents": ["root"],
        "body": b"%PDF-1.4\n% fake-gdrive sample\nArchitecture summary here.\n%%EOF",
    },
    "folder-1": {
        "id": "folder-1",
        "name": "Engineering",
        "mimeType": "application/vnd.google-apps.folder",
        "modifiedTime": "2026-01-01T00:00:00.000Z",
        "size": "0",
        "parents": ["root"],
        "body": None,
    },
}


def file_metadata(file_id: str) -> dict | None:
    record = FAKE_FILES.get(file_id)
    if record is None:
        return None
    return {k: v for k, v in record.items() if k not in {"body"}}


def file_body(file_id: str) -> bytes | None:
    record = FAKE_FILES.get(file_id)
    if record is None:
        return None
    body = record.get("body")
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    return str(body).encode("utf-8")


def list_files() -> list[dict]:
    return [file_metadata(fid) for fid in FAKE_FILES if file_metadata(fid) is not None]
