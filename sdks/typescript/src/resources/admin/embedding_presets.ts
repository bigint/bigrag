import type { RequestClient } from "../../core.js";
import type {
  CreateEmbeddingPresetBody,
  EmbeddingPreset,
  EmbeddingPresetListResponse,
  StatusResponse,
  UpdateEmbeddingPresetBody,
} from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminEmbeddingPresetsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<EmbeddingPresetListResponse> {
    return this._client._request("GET", "/v1/admin/embedding-presets", {
      params: pagination(options),
    });
  }

  create(body: CreateEmbeddingPresetBody): Promise<EmbeddingPreset> {
    return this._client._request("POST", "/v1/admin/embedding-presets", { json: body });
  }

  update(presetId: string, body: UpdateEmbeddingPresetBody): Promise<EmbeddingPreset> {
    return this._client._request(
      "PATCH",
      `/v1/admin/embedding-presets/${encodeURIComponent(presetId)}`,
      { json: body },
    );
  }

  test(body: {
    provider: string;
    model: string;
    api_key?: string | null;
    base_url?: string | null;
  }): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/admin/embedding-presets/test", { json: body });
  }

  testSaved(presetId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/admin/embedding-presets/${encodeURIComponent(presetId)}/test`,
    );
  }

  delete(presetId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/admin/embedding-presets/${encodeURIComponent(presetId)}`,
    );
  }
}
