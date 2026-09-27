/** Release manifest written by the pipeline (ADR-0002). Only the fields the shell reads so far. */
export interface ManifestFile {
  family: string;
  bytes: number;
  sha256: string;
}

export interface Manifest {
  schema_version: number;
  dataset: { name: string; title: string; license: string; synthetic: boolean };
  counts: Record<string, number>;
  files: Record<string, ManifestFile>;
}

/** Decode a uint16-quantized value back to physical units: v = offset + q · scale. */
export function dequantize(q: number, offset: number, scale: number): number {
  return offset + q * scale;
}

export function isManifest(value: unknown): value is Manifest {
  if (typeof value !== "object" || value === null) return false;
  const m = value as Partial<Manifest>;
  return (
    m.schema_version === 1 && typeof m.dataset?.name === "string" && typeof m.files === "object"
  );
}
