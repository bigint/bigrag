"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { type CreateS3JobBody, useCreateS3Job } from "@/hooks/use-s3-jobs";

interface Props {
  readonly collection: string;
  readonly open: boolean;
  readonly onClose: () => void;
}

const SUPPORTED_FILE_TYPES = ["pdf", "docx", "pptx", "xlsx", "md", "txt", "html", "csv", "json"];

export const S3JobForm = ({ collection, open, onClose }: Props) => {
  const create = useCreateS3Job(collection);

  const [bucket, setBucket] = useState("");
  const [prefix, setPrefix] = useState("");
  const [region, setRegion] = useState("us-east-1");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [noSignRequest, setNoSignRequest] = useState(false);
  const [fileTypes, setFileTypes] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setBucket("");
    setPrefix("");
    setRegion("us-east-1");
    setEndpointUrl("");
    setAccessKey("");
    setSecretKey("");
    setNoSignRequest(false);
    setFileTypes(new Set());
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const toggleType = (type: string) => {
    setFileTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    const cleanBucket = bucket.trim();
    if (!cleanBucket) return setError("Bucket is required");

    if (!noSignRequest && (accessKey || secretKey) && !(accessKey && secretKey)) {
      return setError("Provide both access key and secret key, or neither");
    }

    const body: CreateS3JobBody = {
      bucket: cleanBucket,
      prefix: prefix.trim(),
      region: region.trim() || "us-east-1",
    };
    if (endpointUrl.trim()) body.endpoint_url = endpointUrl.trim();
    if (noSignRequest) {
      body.no_sign_request = true;
    } else if (accessKey && secretKey) {
      body.access_key = accessKey;
      body.secret_key = secretKey;
    }
    if (fileTypes.size > 0) body.file_types = Array.from(fileTypes);

    try {
      await create.mutateAsync(body);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start S3 job");
    }
  };

  return (
    <Modal onClose={handleClose} open={open} size="lg" title="Ingest from S3">
      <form className="space-y-4" onSubmit={handleSubmit}>
        {error && (
          <div
            className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            role="alert"
          >
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input
            id="s3-bucket"
            label="Bucket"
            name="bucket"
            onChange={(e) => setBucket(e.target.value)}
            placeholder="my-bucket"
            required
            value={bucket}
          />
          <Input
            id="s3-region"
            label="Region"
            name="region"
            onChange={(e) => setRegion(e.target.value)}
            placeholder="us-east-1"
            value={region}
          />
        </div>

        <Input
          description="Only ingest objects under this key prefix. Leave blank to scan the whole bucket."
          id="s3-prefix"
          label="Prefix"
          name="prefix"
          onChange={(e) => setPrefix(e.target.value)}
          placeholder="reports/2026/"
          value={prefix}
        />

        <Input
          description="For S3-compatible services (MinIO, R2, Spaces). Leave blank for AWS S3."
          id="s3-endpoint"
          label="Endpoint URL"
          name="endpoint_url"
          onChange={(e) => setEndpointUrl(e.target.value)}
          placeholder="https://s3.example.com"
          type="url"
          value={endpointUrl}
        />

        <div className="space-y-2 rounded-md border border-border p-3">
          <Checkbox
            checked={noSignRequest}
            id="s3-anonymous"
            label="Public bucket (no credentials)"
            onCheckedChange={(v) => setNoSignRequest(!!v)}
          />
          <p className="pl-6 text-xs text-muted-foreground">
            Skips signing and ignores any provided credentials.
          </p>
          {!noSignRequest && (
            <div className="grid grid-cols-1 gap-3 pt-2 md:grid-cols-2">
              <Input
                autoComplete="off"
                id="s3-access-key"
                label="Access key"
                name="access_key"
                onChange={(e) => setAccessKey(e.target.value)}
                placeholder="AKIA…"
                value={accessKey}
              />
              <Input
                autoComplete="off"
                id="s3-secret-key"
                label="Secret key"
                name="secret_key"
                onChange={(e) => setSecretKey(e.target.value)}
                placeholder="••••••••"
                type="password"
                value={secretKey}
              />
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <span className="text-sm font-medium">File types</span>
          <p className="text-xs text-muted-foreground">
            Leave all unchecked to ingest every supported type.
          </p>
          <div className="grid grid-cols-3 gap-2 rounded-md border border-border p-3 md:grid-cols-5">
            {SUPPORTED_FILE_TYPES.map((type) => (
              <Checkbox
                checked={fileTypes.has(type)}
                id={`s3-type-${type}`}
                key={type}
                label={`.${type}`}
                onCheckedChange={() => toggleType(type)}
              />
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button onClick={handleClose} type="button" variant="secondary">
            Cancel
          </Button>
          <Button disabled={create.isPending} type="submit">
            {create.isPending ? "Starting…" : "Start ingestion"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
