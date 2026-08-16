import type { HealthResponse, LookBuildResponse, SavedLook, TryOnJob, UserProfile } from "./types";

export const API_ORIGIN = "http://127.0.0.1:8000";

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
  profile: () => request<UserProfile | null>("/api/profile"),
  uploadPhoto: (photo: File) => {
    const data = new FormData();
    data.append("photo", photo);
    return request<UserProfile>("/api/profile/photo", { method: "POST", body: data });
  },
  createLook: async (captureDataUrl: string, sourceUrl: string | null) => {
    const blob = await fetch(captureDataUrl).then((response) => response.blob());
    const data = new FormData();
    data.append("capture", blob, "capture.jpg");
    if (sourceUrl?.startsWith("http")) data.append("source_url", sourceUrl);
    return request<LookBuildResponse>("/api/looks", { method: "POST", body: data });
  },
  createTryOn: (lookId: string, selections: Record<string, number>) =>
    request<TryOnJob>("/api/try-ons", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ look_id: lookId, selections }),
    }),
  tryOn: (jobId: string) => request<TryOnJob>(`/api/try-ons/${jobId}`),
  saveLook: (look: LookBuildResponse, personalizedResultRef: string | null) =>
    request<SavedLook>("/api/saved-looks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_url: look.source_url,
        capture_ref: look.capture_ref,
        personalized_result_ref: personalizedResultRef,
        snapshot: look.result,
      }),
    }),
  savedLooks: () => request<SavedLook[]>("/api/saved-looks"),
  deleteSavedLook: (savedId: string) =>
    request<void>(`/api/saved-looks/${savedId}`, { method: "DELETE" }),
};

export function mediaUrl(ref: string): string {
  return ref.startsWith("http") ? ref : `${API_ORIGIN}${ref}`;
}
