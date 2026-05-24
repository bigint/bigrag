import type { RequestClient } from "../core.js";
import type {
  ChangePasswordBody,
  LoginBody,
  PreferencesResponse,
  SessionResponse,
  SetupBody,
  SetupStatusResponse,
  StatusResponse,
  WhoamiResponse,
} from "../types/index.js";

export class AuthResource {
  constructor(private readonly _client: RequestClient) {}

  setupStatus(): Promise<SetupStatusResponse> {
    return this._client._request("GET", "/v1/auth/setup-status");
  }

  setup(body: SetupBody): Promise<SessionResponse> {
    return this._client._request("POST", "/v1/auth/setup", { json: body });
  }

  login(body: LoginBody): Promise<SessionResponse> {
    return this._client._request("POST", "/v1/auth/login", { json: body });
  }

  logout(): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/auth/logout");
  }

  logoutAll(): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/auth/logout-all");
  }

  me(): Promise<SessionResponse> {
    return this._client._request("GET", "/v1/auth/me");
  }

  whoami(): Promise<WhoamiResponse> {
    return this._client._request("GET", "/v1/auth/whoami");
  }

  changePassword(body: ChangePasswordBody): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/auth/password", { json: body });
  }

  getPreferences(): Promise<PreferencesResponse> {
    return this._client._request("GET", "/v1/auth/preferences");
  }

  updatePreferences(data: Record<string, unknown>): Promise<PreferencesResponse> {
    return this._client._request("PUT", "/v1/auth/preferences", { json: { data } });
  }
}
