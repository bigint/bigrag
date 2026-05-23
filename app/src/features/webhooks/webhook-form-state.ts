export type WebhookFormValues = {
  events: string[];
  url: string;
};

export const WEBHOOK_EVENT_CATEGORIES: Record<string, string[]> = {
  Documents: ["document.processing", "document.ready", "document.failed", "document.deleted"],
  Collections: [
    "collection.created",
    "collection.updated",
    "collection.deleted",
    "collection.truncated",
  ],
  Connectors: ["connector.sync.started", "connector.sync.completed", "connector.sync.failed"],
  Backups: ["backup.started", "backup.succeeded", "backup.failed"],
};

const DEFAULT_WEBHOOK_EVENTS = Object.values(WEBHOOK_EVENT_CATEGORIES).flat();

export const defaultWebhookFormValues = (): WebhookFormValues => ({
  events: [...DEFAULT_WEBHOOK_EVENTS],
  url: "",
});

export const toggleWebhookEvent = (
  selectedEvents: readonly string[],
  eventName: string,
): string[] => {
  if (selectedEvents.includes(eventName)) {
    return selectedEvents.filter((event) => event !== eventName);
  }
  return [...selectedEvents, eventName];
};

export const toggleWebhookCategory = (
  selectedEvents: readonly string[],
  categoryEvents: readonly string[],
): string[] => {
  const removeCategory = categoryEvents.every((event) => selectedEvents.includes(event));
  if (removeCategory) {
    return selectedEvents.filter((event) => !categoryEvents.includes(event));
  }
  return Array.from(new Set([...selectedEvents, ...categoryEvents]));
};

export const validateWebhookUrl = (url: string): string | undefined => {
  const trimmedUrl = url.trim();
  if (!trimmedUrl) return "URL is required";
  try {
    const parsed = new URL(trimmedUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "Webhook URL must use http or https";
    }
  } catch {
    return "Please enter a valid URL";
  }
  return undefined;
};

export const validateWebhookFormValues = ({ events, url }: WebhookFormValues): string | undefined =>
  validateWebhookUrl(url) ?? (events.length === 0 ? "Select at least one event" : undefined);
