import { describe, expect, it } from "vitest";
import {
  defaultWebhookFormValues,
  toggleWebhookCategory,
  toggleWebhookEvent,
  validateWebhookFormValues,
  validateWebhookUrl,
  WEBHOOK_EVENT_CATEGORIES,
} from "./webhook-form-state";

describe("webhook form state", () => {
  it("defaults to every supported event", () => {
    expect(defaultWebhookFormValues().events).toEqual(
      Object.values(WEBHOOK_EVENT_CATEGORIES).flat(),
    );
  });

  it("toggles one event without mutating the previous value", () => {
    const initial = ["document.ready"];

    expect(toggleWebhookEvent(initial, "document.ready")).toEqual([]);
    expect(toggleWebhookEvent(initial, "document.failed")).toEqual([
      "document.ready",
      "document.failed",
    ]);
    expect(initial).toEqual(["document.ready"]);
  });

  it("toggles category events as a set", () => {
    const events = WEBHOOK_EVENT_CATEGORIES.Documents;

    expect(toggleWebhookCategory([], events)).toEqual(events);
    expect(toggleWebhookCategory(events, events)).toEqual([]);
  });

  it("validates webhook URL and event selection", () => {
    expect(validateWebhookUrl("")).toBe("URL is required");
    expect(validateWebhookUrl("ftp://example.com/hook")).toBe("Webhook URL must use http or https");
    expect(validateWebhookUrl("https://example.com/hook")).toBeUndefined();
    expect(
      validateWebhookFormValues({
        description: "",
        events: [],
        url: "https://example.com/hook",
      }),
    ).toBe("Select at least one event");
  });
});
