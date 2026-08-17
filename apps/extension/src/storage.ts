import { mediaUrl } from "./api";
import type { LookBuildResponse, SavedLook, UserProfile } from "./types";

const DATABASE = "want-private";
const VERSION = 1;
const PROFILES = "profiles";
const SAVED_LOOKS = "saved-looks";

export const localStore = {
  async profile(): Promise<UserProfile | null> {
    return (await get<UserProfile>(PROFILES, "current")) ?? null;
  },

  async saveProfile(photo: File): Promise<UserProfile> {
    const existing = await this.profile();
    const now = new Date().toISOString();
    const profile = {
      photo_ref: await toDataUrl(photo),
      created_at: existing?.created_at ?? now,
      updated_at: now,
    };
    await put(PROFILES, profile, "current");
    return profile;
  },

  async savedLooks(): Promise<SavedLook[]> {
    const database = await openDatabase();
    return new Promise((resolve, reject) => {
      const request = database.transaction(SAVED_LOOKS, "readonly").objectStore(SAVED_LOOKS).getAll();
      request.onsuccess = () => resolve((request.result as SavedLook[]).sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
      request.onerror = () => reject(request.error);
    });
  },

  async saveLook(look: LookBuildResponse, personalizedResultRef: string | null): Promise<SavedLook> {
    const now = new Date().toISOString();
    const saved: SavedLook = {
      id: crypto.randomUUID(),
      source_url: look.source_url,
      capture_ref: look.capture_ref,
      personalized_result_ref: personalizedResultRef ? await cacheMedia(personalizedResultRef) : null,
      snapshot: look.result,
      created_at: now,
      updated_at: now,
    };
    await put(SAVED_LOOKS, saved);
    return saved;
  },

  async deleteSavedLook(id: string): Promise<void> {
    const database = await openDatabase();
    await complete(database.transaction(SAVED_LOOKS, "readwrite").objectStore(SAVED_LOOKS).delete(id));
  },
};

export async function localizeLook(look: LookBuildResponse): Promise<LookBuildResponse> {
  const captureRef = await cacheMedia(look.capture_ref);
  const items = await Promise.all(look.result.items.map(async (item) => ({
    ...item,
    crop_ref: await cacheMedia(item.crop_ref),
    products: await Promise.all(item.products.map(async (product) => ({
      ...product,
      image_ref: product.image_ref ? await cacheMedia(product.image_ref) : product.image_ref,
    }))),
  })));
  return { ...look, capture_ref: captureRef, result: { ...look.result, items } };
}

export async function cacheMedia(ref: string): Promise<string> {
  if (ref.startsWith("data:") || ref.startsWith("blob:")) return ref;
  const response = await fetch(mediaUrl(ref));
  if (!response.ok) throw new Error(`Could not preserve an image (${response.status})`);
  return toDataUrl(await response.blob());
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(PROFILES)) database.createObjectStore(PROFILES);
      if (!database.objectStoreNames.contains(SAVED_LOOKS)) database.createObjectStore(SAVED_LOOKS, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function get<T>(store: string, key: IDBValidKey): Promise<T | undefined> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = database.transaction(store, "readonly").objectStore(store).get(key);
    request.onsuccess = () => resolve(request.result as T | undefined);
    request.onerror = () => reject(request.error);
  });
}

async function put(store: string, value: unknown, key?: IDBValidKey): Promise<void> {
  const database = await openDatabase();
  const objectStore = database.transaction(store, "readwrite").objectStore(store);
  const request = key === undefined ? objectStore.put(value) : objectStore.put(value, key);
  await complete(request);
}

function complete(request: IDBRequest): Promise<void> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function toDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read image"));
    reader.readAsDataURL(blob);
  });
}
