export interface HealthResponse {
  status: string;
  service: string;
}

export interface UserProfile {
  photo_ref: string;
  created_at: string;
  updated_at: string;
}

export interface CaptureRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PendingCapture {
  dataUrl: string;
  rect: CaptureRect;
  viewport: { width: number; height: number };
  devicePixelRatio: number;
  sourceImage?: {
    url: string;
    renderedRect: CaptureRect;
    naturalWidth: number;
    naturalHeight: number;
  };
  sourceVideo?: {
    dataUrl: string;
    renderedRect: CaptureRect;
    naturalWidth: number;
    naturalHeight: number;
  };
  sourceUrl: string | null;
  capturedAt: string;
}

export type BodySlot = "upper_body" | "lower_body" | "full_body" | "shoes" | "accessory";

export interface GarmentAnalysis {
  item_id: string;
  body_slot: BodySlot;
  category: string;
  box_2d: number[];
  visibility: "clear" | "partial" | "heavily_occluded";
  visible_fraction: number;
  colors: string[];
  silhouette: string;
  material_appearance: string;
  pattern: string;
  print_or_graphic: string;
  details: string[];
}

export interface ProductMatch {
  match_kind: "exact" | "similar";
  title: string;
  retailer: string;
  price_minor: number | null;
  currency: string | null;
  image_url: string;
  image_ref?: string | null;
  product_url: string;
}

export interface ItemResult {
  item_id: string;
  crop_ref: string;
  products: ProductMatch[];
  selected_index: number;
  give_up_reason: string | null;
}

export interface LookBuildResponse {
  look_id: string;
  source_url: string | null;
  capture_ref: string;
  result: {
    analysis: {
      garments: GarmentAnalysis[];
    };
    items: ItemResult[];
  };
}

export interface TryOnJob {
  id: string;
  look_id: string;
  status: "queued" | "running" | "success" | "failed";
  stage: string;
  result_ref: string | null;
  error: string | null;
  rendered_garment_item_ids: string[];
}

export interface SavedLook {
  id: string;
  source_url: string | null;
  capture_ref: string;
  personalized_result_ref: string | null;
  snapshot: LookBuildResponse["result"];
  created_at: string;
  updated_at: string;
}

export type ExtensionMessage =
  | { type: "START_CAPTURE" }
  | { type: "GET_PENDING_CAPTURE" }
  | { type: "CLEAR_PENDING_CAPTURE" }
  | { type: "CAPTURE_READY"; capture: PendingCapture }
  | { type: "CAPTURE_FAILED"; error: string }
  | {
      type: "SELECTION_CONFIRMED";
      rect: CaptureRect;
      viewport: { width: number; height: number };
      devicePixelRatio: number;
      sourceImage?: PendingCapture["sourceImage"];
      sourceVideo?: PendingCapture["sourceVideo"];
    };
