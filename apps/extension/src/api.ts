import type { HealthResponse, LookBuildResponse, TryOnJob } from "./types";

export const API_ORIGIN =
  import.meta.env.VITE_API_ORIGIN?.replace(/\/$/, "") || "http://127.0.0.1:8000";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ORIGIN}${path}`, init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  createLook: async (captureDataUrl: string, sourceUrl: string | null) => {
    const blob = await fetch(captureDataUrl).then((response) => response.blob());
    const data = new FormData();
    data.append("capture", blob, "capture.jpg");
    if (sourceUrl?.startsWith("http")) data.append("source_url", sourceUrl);
    return request<LookBuildResponse>("/api/looks", { method: "POST", body: data });
  },
  createTryOn: async (look: LookBuildResponse, selections: Record<string, number>, profileRef: string) => {
    const data = new FormData();
    data.append("person", await fetch(profileRef).then((response) => response.blob()), "person.jpg");
    const portableLook = {
      ...look,
      capture_ref: "browser-local",
      result: {
        ...look.result,
        items: look.result.items.map((item) => ({
          ...item,
          crop_ref: "browser-local",
          products: item.products.map((product) => ({ ...product, image_ref: null })),
        })),
      },
    };
    data.append("look", JSON.stringify(portableLook));
    data.append("selections", JSON.stringify(selections));
    const referenceItemIds: string[] = [];
    for (const item of look.result.items) {
      const selected = selections[item.item_id] ?? item.selected_index;
      const product = item.products[selected];
      if (!product) continue;
      const ref = product.image_ref ?? product.image_url;
      const blob = await fetch(mediaUrl(ref)).then((response) => {
        if (!response.ok) throw new Error(`Could not prepare ${product.title}`);
        return response.blob();
      });
      referenceItemIds.push(item.item_id);
      data.append("references", blob, `${referenceItemIds.length}.jpg`);
    }
    data.append("reference_item_ids", JSON.stringify(referenceItemIds));
    return request<TryOnJob>("/api/try-ons", { method: "POST", body: data });
  },
  tryOn: (jobId: string) => request<TryOnJob>(`/api/try-ons/${jobId}`),
};

export function mediaUrl(ref: string): string {
  return /^(?:https?|data|blob):/.test(ref) ? ref : `${API_ORIGIN}${ref}`;
}
