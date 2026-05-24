export interface SetupStatusResponse {
  needs_setup: boolean;
}

export interface LoginBody {
  email: string;
  password: string;
}

export interface SetupBody {
  email: string;
  password: string;
  display_name?: string;
}

export interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionResponse {
  user: User;
}

export interface WhoamiResponse {
  authenticated: boolean;
  auth_method: string;
  user_id: string;
  user_email: string;
  api_key_id: string | null;
  api_key_name: string | null;
  scopes: string[] | null;
  collection: string | null;
}

export interface PreferencesResponse {
  data: Record<string, unknown>;
}
