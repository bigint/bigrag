import type { RequestClient } from "../../core.js";
import type {
  CreateUserBody,
  StatusResponse,
  UpdateUserBody,
  User,
  UserListResponse,
} from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminUsersResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<UserListResponse> {
    return this._client._request("GET", "/v1/admin/users", { params: pagination(options) });
  }

  create(body: CreateUserBody): Promise<User> {
    return this._client._request("POST", "/v1/admin/users", { json: body });
  }

  update(userId: string, body: UpdateUserBody): Promise<User> {
    return this._client._request("PATCH", `/v1/admin/users/${encodeURIComponent(userId)}`, {
      json: body,
    });
  }

  delete(userId: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/users/${encodeURIComponent(userId)}`);
  }
}
