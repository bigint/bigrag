import type { RequestClient } from "../../core.js";
import type { BackupCreateBody, BackupJob, BackupJobListResponse } from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminBackupsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<BackupJobListResponse> {
    return this._client._request("GET", "/v1/admin/backups", { params: pagination(options) });
  }

  get(backupId: string): Promise<BackupJob> {
    return this._client._request("GET", `/v1/admin/backups/${encodeURIComponent(backupId)}`);
  }

  create(body: BackupCreateBody = {}): Promise<BackupJob> {
    return this._client._request("POST", "/v1/admin/backups", {
      json: { label: body.label ?? "" },
    });
  }
}
