import { describe, expect, it } from "vitest";
import {
  defaultGoogleConnectorFormValues,
  googleConnectorPayload,
  validateGoogleConnectorFormValues,
} from "./google-connector-form-state";

describe("google connector form state", () => {
  it("creates empty and server-backed defaults", () => {
    expect(defaultGoogleConnectorFormValues()).toEqual({
      clientId: "",
      clientSecret: "",
      enabled: true,
    });
    expect(
      defaultGoogleConnectorFormValues({
        callback_url: "http://localhost:4000/callback",
        client_id: "client-id",
        configured: true,
        created_at: null,
        enabled: false,
        has_client_secret: true,
        provider: "google_drive",
        updated_at: null,
      }),
    ).toEqual({
      clientId: "client-id",
      clientSecret: "",
      enabled: false,
    });
  });

  it("requires a client ID only while enabled", () => {
    expect(
      validateGoogleConnectorFormValues({ clientId: "", clientSecret: "", enabled: true }),
    ).toBe("OAuth client ID is required when enabled");
    expect(
      validateGoogleConnectorFormValues({ clientId: "", clientSecret: "", enabled: false }),
    ).toBeUndefined();
  });

  it("builds the API payload with trimmed credentials", () => {
    expect(
      googleConnectorPayload({
        clientId: " client-id ",
        clientSecret: " secret ",
        enabled: true,
      }),
    ).toEqual({
      client_id: "client-id",
      client_secret: "secret",
      enabled: true,
    });
    expect(
      googleConnectorPayload({
        clientId: "client-id",
        clientSecret: "",
        enabled: true,
      }),
    ).toEqual({
      client_id: "client-id",
      client_secret: null,
      enabled: true,
    });
  });
});
