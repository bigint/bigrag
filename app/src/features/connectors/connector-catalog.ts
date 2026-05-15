import type { LucideIcon } from "lucide-react";
import { Building2, Cloud, Folder, HardDrive } from "lucide-react";

export type ConnectorProviderId = "google-drive" | "sharepoint" | "onedrive" | "s3-r2";
export type ConnectorAvailability = "available" | "planned";
export type ConnectorStatusVariant =
  | "error"
  | "info"
  | "neutral"
  | "primary"
  | "success"
  | "warning";

export type ConnectorProvider = {
  readonly id: ConnectorProviderId;
  readonly label: string;
  readonly shortLabel: string;
  readonly category: string;
  readonly description: string;
  readonly availability: ConnectorAvailability;
  readonly icon: LucideIcon;
  readonly collectionSegment?: string;
  readonly setupItems: readonly string[];
  readonly capabilities: readonly string[];
};

export type CollectionConnectorProvider = ConnectorProvider & {
  readonly collectionSegment: string;
};

export type ConnectorStatus = {
  readonly label: string;
  readonly detail: string;
  readonly variant: ConnectorStatusVariant;
};

export const connectorProviders = [
  {
    id: "google-drive",
    label: "Google Drive",
    shortLabel: "Drive",
    category: "Cloud storage",
    description: "Sync selected files and folders from a connected workspace account.",
    availability: "available",
    icon: Cloud,
    collectionSegment: "google-drive",
    setupItems: ["OAuth client", "Callback URL", "User account"],
    capabilities: ["Browse remote files", "Sync folders", "Schedule refreshes"],
  },
  {
    id: "sharepoint",
    label: "SharePoint",
    shortLabel: "SharePoint",
    category: "Cloud storage",
    description: "Sync Microsoft site document libraries into collections.",
    availability: "planned",
    icon: Building2,
    setupItems: ["Tenant app", "Callback URL", "Site account"],
    capabilities: ["Library sync", "Folder selection", "Scheduled refreshes"],
  },
  {
    id: "onedrive",
    label: "OneDrive",
    shortLabel: "OneDrive",
    category: "Cloud storage",
    description: "Sync personal and shared drive folders into collections.",
    availability: "planned",
    icon: Folder,
    setupItems: ["OAuth app", "Callback URL", "Drive account"],
    capabilities: ["File sync", "Folder selection", "Manual refreshes"],
  },
  {
    id: "s3-r2",
    label: "S3 / R2",
    shortLabel: "S3 / R2",
    category: "Object storage",
    description: "Import object prefixes from S3-compatible buckets.",
    availability: "planned",
    icon: HardDrive,
    setupItems: ["Access policy", "Bucket", "Prefix"],
    capabilities: ["Object import", "Prefix scoping", "Scheduled refreshes"],
  },
] as const satisfies readonly ConnectorProvider[];

export const availableConnectorProviders = connectorProviders.filter(
  (provider) => provider.availability === "available",
);

const isCollectionConnectorProvider = (
  provider: ConnectorProvider,
): provider is CollectionConnectorProvider => Boolean(provider.collectionSegment);

export const collectionConnectorProviders = availableConnectorProviders.filter(
  isCollectionConnectorProvider,
);

export const defaultConnectorProvider = connectorProviders[0];

export const connectorProviderById = (id: ConnectorProviderId) =>
  connectorProviders.find((provider) => provider.id === id) ?? defaultConnectorProvider;

export const connectorCollectionHref = (
  collectionName: string,
  provider: CollectionConnectorProvider,
) => `/collections/${encodeURIComponent(collectionName)}/connectors/${provider.collectionSegment}`;

export const connectorStatus = ({
  availability,
  configured = false,
  connected = false,
  enabled = false,
  needsReauth = false,
}: {
  availability: ConnectorAvailability;
  configured?: boolean;
  connected?: boolean;
  enabled?: boolean;
  needsReauth?: boolean;
}): ConnectorStatus => {
  if (availability === "planned") {
    return {
      label: "planned",
      detail: "Provider runtime is not installed yet",
      variant: "neutral",
    };
  }

  if (!configured) {
    return {
      label: "setup required",
      detail: "Credentials are missing",
      variant: "warning",
    };
  }

  if (!enabled) {
    return {
      label: "disabled",
      detail: "Credentials are saved but the provider is off",
      variant: "neutral",
    };
  }

  if (needsReauth) {
    return {
      label: "reconnect",
      detail: "The connected account needs OAuth refresh",
      variant: "warning",
    };
  }

  if (connected) {
    return {
      label: "connected",
      detail: "Credentials and account are ready",
      variant: "success",
    };
  }

  return {
    label: "ready",
    detail: "Credentials are saved",
    variant: "primary",
  };
};
