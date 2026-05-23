import type { LucideIcon } from "lucide-react";
import { HardDrive } from "lucide-react";

type ConnectorProviderId = "s3";
type ConnectorStatusVariant = "neutral" | "primary" | "success";

export type ConnectorProvider = {
  readonly id: ConnectorProviderId;
  readonly label: string;
  readonly shortLabel: string;
  readonly category: string;
  readonly description: string;
  readonly icon: LucideIcon;
  readonly collectionSegment: string;
  readonly setupItems: readonly string[];
  readonly capabilities: readonly string[];
};

type ConnectorStatus = {
  readonly label: string;
  readonly detail: string;
  readonly variant: ConnectorStatusVariant;
};

export const connectorProviders = [
  {
    id: "s3",
    label: "S3 / R2",
    shortLabel: "S3 / R2",
    category: "Object storage",
    description: "Mirror object prefixes into collections.",
    icon: HardDrive,
    collectionSegment: "s3",
    setupItems: ["Bucket", "Prefix", "Access policy"],
    capabilities: ["Prefix mirror", "Manual sync", "Scheduled sync"],
  },
] as const satisfies readonly ConnectorProvider[];

export const collectionConnectorProviders = connectorProviders;

export const defaultConnectorProvider = connectorProviders[0];

export const connectorProviderById = (id: ConnectorProviderId) =>
  connectorProviders.find((provider) => provider.id === id) ?? defaultConnectorProvider;

export const connectorCollectionHref = (collectionName: string, provider: ConnectorProvider) =>
  `/collections/${encodeURIComponent(collectionName)}/connectors/${provider.collectionSegment}`;

export const connectorStatus = (sourceCount: number): ConnectorStatus => {
  if (sourceCount > 0) {
    return {
      label: "configured",
      detail: `${sourceCount.toLocaleString()} source${sourceCount === 1 ? "" : "s"}`,
      variant: "success",
    };
  }
  return {
    label: "ready",
    detail: "No sources configured",
    variant: "primary",
  };
};
