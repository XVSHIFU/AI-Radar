export type ResearchArtifact = {
  id: string; run_id: string; name: string; mime: string; size_bytes: number;
  download_url: string; expires_at: string; citation_index: number;
  dataset_ids: string[]; as_of: string; timezone: string;
};
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const mimes: Record<string, string> = { json: "application/json", csv: "text/csv", png: "image/png" };
export function artifactsFrom(value: unknown, runId?: string, indices?: number[]): ResearchArtifact[] {
  if (!Array.isArray(value) || value.length > 8) throw new Error("Invalid artifacts");
  let bytes = 0;
  const ids = new Set<string>();
  for (const item of value) {
    if (!item || typeof item !== "object" || typeof item.id !== "string" || !uuid.test(item.id) ||
        typeof item.run_id !== "string" || !uuid.test(item.run_id) || (runId && item.run_id !== runId) ||
        ids.has(item.id) || typeof item.name !== "string" ||
        !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}\.(json|csv|png)$/.test(item.name) ||
        item.mime !== mimes[item.name.split(".").at(-1)!] ||
        !Number.isSafeInteger(item.size_bytes) || item.size_bytes < 0 ||
        !Number.isInteger(item.citation_index) || item.citation_index < 1 || item.citation_index > 60 ||
        (indices && !indices.includes(item.citation_index)) ||
        item.download_url !== `/api/v1/assistant/runs/${item.run_id}/artifacts/${item.id}` ||
        typeof item.expires_at !== "string" || !Number.isFinite(Date.parse(item.expires_at)) ||
        typeof item.as_of !== "string" || typeof item.timezone !== "string" ||
        !Array.isArray(item.dataset_ids) || item.dataset_ids.length < 1 || item.dataset_ids.length > 4 ||
        item.dataset_ids.some((id: unknown) => typeof id !== "string" || !uuid.test(id)))
      throw new Error("Invalid artifact provenance");
    ids.add(item.id); bytes += item.size_bytes;
  }
  if (bytes > 1048576) throw new Error("Artifact size exceeded");
  return value as ResearchArtifact[];
}

export async function fetchArtifact(item: ResearchArtifact, signal: AbortSignal): Promise<Blob> {
  artifactsFrom([item]);
  if (Date.now() >= Date.parse(item.expires_at)) throw new Error("expired");
  const response = await fetch(item.download_url, {credentials: "same-origin", redirect: "error",
                                                 cache: "no-store", signal});
  if (response.status === 404) throw new Error("expired");
  if (!response.ok || !response.body || response.headers.get("content-type")?.split(";")[0] !== item.mime)
    throw new Error("unavailable");
  const reader = response.body.getReader();
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  let size = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.byteLength;
      if (size > 1048576 || size > item.size_bytes) throw new Error("unavailable");
      chunks.push(new Uint8Array(next.value));
    }
    if (size !== item.size_bytes) throw new Error("unavailable");
    return new Blob(chunks, {type: item.mime});
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
