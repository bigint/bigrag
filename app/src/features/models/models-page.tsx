import { useNavigate } from "@tanstack/react-router";
import { Cpu, Pencil, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Page } from "@/components/ui/page";
import { Tabs } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";
import { MODEL_SETTINGS_GROUPS, type ModelsTab } from "@/features/models/model-tabs";
import { PresetForm } from "@/features/models/preset-form";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { useDeleteEmbeddingPreset, useEmbeddingPresets } from "@/hooks/use-embedding-presets";
import { formatRelative } from "@/lib/format";
import type { EmbeddingPreset, InstanceSettingGroup } from "@/types/bigrag";

const MODEL_TABS = [
  { icon: Cpu, label: "Embedding presets", value: "presets" },
  { icon: SlidersHorizontal, label: "Runtime settings", value: "settings" },
];

type ModelsPageProps = {
  readonly activeTab: ModelsTab;
  readonly focusGroup: InstanceSettingGroup | undefined;
};

export const ModelsPage = ({ activeTab, focusGroup }: ModelsPageProps) => {
  const navigate = useNavigate();
  const { data, error, isError, isPending, refetch } = useEmbeddingPresets();
  const remove = useDeleteEmbeddingPreset();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<EmbeddingPreset | null>(null);
  const [deleteFor, setDeleteFor] = useState<EmbeddingPreset | null>(null);

  const openEdit = (p: EmbeddingPreset) => {
    setEditing(p);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditing(null);
  };

  const setTab = (value: string) => {
    const tab = value as ModelsTab;
    navigate({
      to: "/models",
      search: tab === "settings" ? { tab: "settings" } : {},
      replace: true,
    });
  };

  const columns: Column<EmbeddingPreset>[] = [
    {
      header: "Name",
      key: "name",
      render: (p) => <span className="text-sm font-medium">{p.name}</span>,
    },
    {
      header: "Provider",
      key: "provider",
      render: (p) => (
        <Badge variant={p.provider === "openai" ? "primary" : "info"}>{p.provider}</Badge>
      ),
    },
    {
      header: "Model",
      key: "model",
      className: "font-mono text-xs text-muted-foreground",
      render: (p) => p.model,
    },
    {
      header: "Dim",
      key: "dimension",
      className: "tabular-nums text-muted-foreground",
      render: (p) => p.dimension,
    },
    {
      header: "Key",
      key: "has_api_key",
      render: (p) =>
        p.has_api_key ? (
          <Badge dot variant="success">
            set
          </Badge>
        ) : (
          <Badge variant="warning">missing</Badge>
        ),
    },
    {
      header: "Updated",
      key: "updated_at",
      className: "text-muted-foreground",
      render: (p) => formatRelative(p.updated_at),
    },
    {
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      key: "actions",
      render: (p) => (
        <div className="flex items-center justify-end gap-1">
          <Tooltip content="Edit preset">
            <Button aria-label="Edit preset" onClick={() => openEdit(p)} size="sm" variant="ghost">
              <Pencil className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Delete preset">
            <Button
              aria-label="Delete preset"
              className="hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setDeleteFor(p)}
              size="sm"
              variant="ghost"
            >
              <Trash2 className="size-4" />
            </Button>
          </Tooltip>
        </div>
      ),
    },
  ];

  return (
    <Page.Shell>
      <Page.Header
        className="mb-0"
        actions={
          activeTab === "presets" ? (
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="size-4" /> New preset
            </Button>
          ) : undefined
        }
        description={
          activeTab === "presets"
            ? "Save embedding presets once and reuse them across collections."
            : "Set fallback embedding, retrieval, and chat provider behavior."
        }
        title="Models"
      />

      <Tabs onChange={setTab} tabs={MODEL_TABS} value={activeTab} />

      {activeTab === "settings" ? (
        <InstanceSettingsTab focusGroup={focusGroup} groups={MODEL_SETTINGS_GROUPS} />
      ) : (
        <DataTable
          columns={columns}
          data={data?.presets ?? []}
          error={isError ? error : null}
          errorAction={
            <Button onClick={() => refetch()} variant="secondary">
              Retry
            </Button>
          }
          errorTitle="Embedding presets unavailable"
          emptyAction={
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="size-4" /> Create your first preset
            </Button>
          }
          emptyDescription="A preset bundles a provider, model, dimension, and API key. Collections pick a preset when they're created."
          emptyIcon={<Cpu className="size-6" />}
          emptyTitle="No embedding presets yet"
          keyExtractor={(p) => p.id}
          loading={isPending}
          loadingMessage="Loading presets…"
        />
      )}

      <PresetForm editing={editing} onClose={closeForm} open={formOpen} />

      <ConfirmDialog
        confirmLabel="Delete"
        description={
          deleteFor
            ? `Delete preset "${deleteFor.name}"? Existing collections that already copied its values keep working — only new collections lose this option.`
            : ""
        }
        loading={remove.isPending}
        onClose={() => setDeleteFor(null)}
        onConfirm={async () => {
          if (!deleteFor) return;
          try {
            await remove.mutateAsync(deleteFor.id);
            setDeleteFor(null);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed");
          }
        }}
        open={!!deleteFor}
        title="Delete embedding preset"
      />
    </Page.Shell>
  );
};
