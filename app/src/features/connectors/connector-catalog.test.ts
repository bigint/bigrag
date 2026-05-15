import { describe, expect, it } from "vitest";
import {
  type ConnectorProviderId,
  collectionConnectorProviders,
  connectorCollectionHref,
  connectorProviderById,
  connectorStatus,
} from "@/features/connectors/connector-catalog";

describe("connector catalog", () => {
  it("routes collection connectors through available providers", () => {
    expect(collectionConnectorProviders.map((provider) => provider.id)).toEqual(["google-drive"]);
    expect(connectorCollectionHref("docs & pdfs", collectionConnectorProviders[0])).toBe(
      "/collections/docs%20%26%20pdfs/connectors/google-drive",
    );
  });

  it("falls back to the default provider for unknown ids", () => {
    expect(connectorProviderById("missing" as ConnectorProviderId).id).toBe("google-drive");
  });

  it("prioritizes connector state labels", () => {
    expect(connectorStatus({ availability: "planned" }).label).toBe("planned");
    expect(connectorStatus({ availability: "available" }).label).toBe("setup required");
    expect(
      connectorStatus({ availability: "available", configured: true, enabled: false }).label,
    ).toBe("disabled");
    expect(
      connectorStatus({
        availability: "available",
        configured: true,
        connected: true,
        enabled: true,
        needsReauth: true,
      }).label,
    ).toBe("reconnect");
    expect(
      connectorStatus({
        availability: "available",
        configured: true,
        connected: true,
        enabled: true,
      }).label,
    ).toBe("connected");
  });
});
