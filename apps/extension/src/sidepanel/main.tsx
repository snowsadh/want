import "@fontsource-variable/archivo";
import "@fontsource-variable/manrope";
import "@fontsource/space-mono/400.css";
import {
  StrictMode,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createRoot } from "react-dom/client";

import { api, mediaUrl } from "../api";
import type {
  ItemResult,
  LookBuildResponse,
  PendingCapture,
  ProductMatch,
  SavedLook,
  TryOnJob,
} from "../types";
import { cropCapture } from "./capture";
import "./styles.css";

type Connection = "checking" | "online" | "offline";

function App() {
  const [connection, setConnection] = useState<Connection>("checking");
  const [setupOpen, setSetupOpen] = useState(false);
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready when you are");
  const [error, setError] = useState<string | null>(null);
  const [capture, setCapture] = useState<{ preview: string; sourceUrl: string | null } | null>(
    null,
  );
  const [look, setLook] = useState<LookBuildResponse | null>(null);
  const [savedLooks, setSavedLooks] = useState<SavedLook[]>([]);
  const [savedOpen, setSavedOpen] = useState(false);
  const [viewingSaved, setViewingSaved] = useState(false);
  const lastCaptureAt = useRef<string | null>(null);

  const consumeCapture = useCallback(async (pending: PendingCapture) => {
    if (lastCaptureAt.current === pending.capturedAt) return;
    lastCaptureAt.current = pending.capturedAt;
    try {
      const preview = await cropCapture(pending);
      setCapture({ preview, sourceUrl: pending.sourceUrl });
      setLook(null);
      setSavedOpen(false);
      setViewingSaved(false);
      setStatus("Look captured");
      setError(null);
    } catch (captureError) {
      setError(readableError(captureError));
    } finally {
      await chrome.runtime.sendMessage({ type: "CLEAR_PENDING_CAPTURE" }).catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    void Promise.all([api.health(), api.profile()])
      .then(([, currentProfile]) => {
        setConnection("online");
        setSetupOpen(!currentProfile);
      })
      .catch(() => {
        setConnection("offline");
        setSetupOpen(true);
      });
    void chrome.runtime
      .sendMessage({ type: "GET_PENDING_CAPTURE" })
      .then((response: { capture?: PendingCapture | null } | undefined) => {
        if (response?.capture) void consumeCapture(response.capture);
      })
      .catch(() => undefined);
    const onRuntimeMessage = (
      message: { type?: string; capture?: PendingCapture; error?: string },
      _sender: chrome.runtime.MessageSender,
      sendResponse: (response?: unknown) => void,
    ) => {
      if (message.type === "CAPTURE_READY" && message.capture) {
        sendResponse({ ok: true });
        void consumeCapture(message.capture);
      }
      if (message.type === "CAPTURE_FAILED") {
        sendResponse({ ok: true });
        setError(message.error ?? "Chrome could not capture this page");
        setStatus("Capture stopped");
      }
      return false;
    };
    chrome.runtime.onMessage.addListener(onRuntimeMessage);
    return () => chrome.runtime.onMessage.removeListener(onRuntimeMessage);
  }, [consumeCapture]);

  async function saveSetup() {
    if (!photo) {
      setError("Choose a full-body photo first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.uploadPhoto(photo);
      setSetupOpen(false);
      setStatus("Photo saved");
    } catch (setupError) {
      setError(readableError(setupError));
    } finally {
      setBusy(false);
    }
  }

  async function startCapture() {
    setError(null);
    setStatus("Drag around a look on the page");
    try {
      const response = (await chrome.runtime.sendMessage({ type: "START_CAPTURE" })) as {
        ok?: boolean;
        error?: string;
      };
      if (!response?.ok) {
        throw new Error(response?.error ?? "Could not start capture on this page");
      }
    } catch (captureError) {
      const message = readableError(captureError);
      setError(
        message.includes("Cannot access contents")
          ? "Chrome blocks capture on this page. Try a regular website."
          : message,
      );
      setStatus("Capture stopped");
    }
  }

  async function findPieces() {
    if (!capture) return;
    setBusy(true);
    setError(null);
    setStatus("Reading the clothes and searching stores…");
    try {
      const response = await api.createLook(capture.preview, capture.sourceUrl);
      setLook(response);
      setStatus("Ready");
    } catch (lookError) {
      setError(readableError(lookError));
      setStatus("Search stopped");
    } finally {
      setBusy(false);
    }
  }

  async function openSavedLooks() {
    setError(null);
    try {
      setSavedLooks(await api.savedLooks());
      setSavedOpen(true);
      setLook(null);
      setCapture(null);
    } catch (savedError) {
      setError(readableError(savedError));
    }
  }

  function openSavedLook(saved: SavedLook) {
    setCapture({
      preview: mediaUrl(saved.personalized_result_ref ?? saved.capture_ref),
      sourceUrl: saved.source_url,
    });
    setLook({
      look_id: saved.id,
      source_url: saved.source_url,
      capture_ref: saved.capture_ref,
      result: saved.snapshot,
    });
    setViewingSaved(true);
    setSavedOpen(false);
  }

  async function deleteSavedLook(savedId: string) {
    try {
      await api.deleteSavedLook(savedId);
      setSavedLooks((current) => current.filter((saved) => saved.id !== savedId));
    } catch (deleteError) {
      setError(readableError(deleteError));
    }
  }

  if (setupOpen) {
    return (
      <Shell>
        <main className="setup">
          <p className="eyebrow">One-time setup</p>
          <h1>Your mirror photo.</h1>
          <label className="photo-drop">
            <span className="bracket top-left" />
            <span className="bracket bottom-right" />
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={(event) => setPhoto(event.target.files?.[0] ?? null)}
            />
            <strong>{photo ? photo.name : "Choose a full-body photo"}</strong>
            <span>JPEG or PNG · 10 MB max</span>
          </label>
          {error && <p className="error">{error}</p>}
          <button className="primary" type="button" disabled={busy || connection !== "online"} onClick={saveSetup}>
            {busy ? "Saving…" : connection === "offline" ? "Unavailable" : "Save photo"}
          </button>
        </main>
      </Shell>
    );
  }

  return (
    <Shell onSaved={openSavedLooks}>
      <main className="home">
        {!look && !savedOpen && (
          <div className="home-intro">
            <h1>See it. Box it. Wear it.</h1>
            <p className="lede">Pick any outfit on the page. WANT! handles the pieces.</p>
          </div>
        )}
        {savedOpen ? (
          <SavedList
            savedLooks={savedLooks}
            onOpen={openSavedLook}
            onDelete={deleteSavedLook}
            onClose={() => setSavedOpen(false)}
          />
        ) : capture && !look ? (
          <section className="capture-card" aria-label="Captured look">
            <div className="capture-frame">
              <img src={capture.preview} alt="Selected look" />
              <span className="bracket top-left" />
              <span className="bracket bottom-right" />
            </div>
            <div className="capture-meta">
              <span className="utility">CAPTURE READY</span>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setCapture(null);
                  setLook(null);
                  setViewingSaved(false);
                }}
              >
                Pick again
              </button>
            </div>
            <button className="primary" type="button" disabled={busy} onClick={findPieces}>
              {busy ? "Working…" : "Find the pieces"}
            </button>
          </section>
        ) : look && capture ? (
          <LookView
            look={look}
            capturePreview={capture.preview}
            onPickAgain={() => {
              setCapture(null);
              setLook(null);
              setViewingSaved(false);
            }}
            allowActions={!viewingSaved}
          />
        ) : (
          <button className="capture-button" type="button" onClick={startCapture}>
            <span className="capture-icon" aria-hidden="true" />
            <span>
              <strong>Pick a look</strong>
              <small>Drag a box on this page</small>
            </span>
          </button>
        )}
        <div className="status-line">
          <span className={`status-dot ${connection}`} />
          <span>{error ?? status}</span>
        </div>
        <button type="button" className="profile-link" onClick={() => setSetupOpen(true)}>
          Change photo
        </button>
      </main>
    </Shell>
  );
}

function Shell({
  children,
  onSaved,
}: {
  children: ReactNode;
  onSaved?: () => void;
}) {
  return (
    <div className="app-shell">
      <header>
        <div className="wordmark">WANT!</div>
        <div className="header-actions">
          {onSaved && (
            <button type="button" className="saved-button" onClick={onSaved}>
              Saved
            </button>
          )}
        </div>
      </header>
      {children}
    </div>
  );
}

function LookView({
  look,
  capturePreview,
  onPickAgain,
  allowActions,
}: {
  look: LookBuildResponse;
  capturePreview: string;
  onPickAgain: () => void;
  allowActions: boolean;
}) {
  const [tryOn, setTryOn] = useState<TryOnJob | null>(null);
  const [tryOnError, setTryOnError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [selections, setSelections] = useState<Record<string, number>>(() =>
    Object.fromEntries(look.result.items.map((item) => [item.item_id, item.selected_index])),
  );
  const garments = new Map(
    look.result.analysis.garments.map((garment) => [garment.item_id, garment]),
  );
  const selectedProducts = productsFor(look.result.items, selections);
  const total = productTotal(selectedProducts);
  const preview = tryOn?.result_ref ? mediaUrl(tryOn.result_ref) : capturePreview;
  const rendering = tryOn?.status === "queued" || tryOn?.status === "running";

  async function startTryOn() {
    setTryOnError(null);
    try {
      let job = await api.createTryOn(look.look_id, selections);
      setTryOn(job);
      while (job.status === "queued" || job.status === "running") {
        await delay(2000);
        job = await api.tryOn(job.id);
        setTryOn(job);
      }
      if (job.status === "failed") setTryOnError(job.error ?? "Try-on stopped");
    } catch (error) {
      setTryOn(null);
      setTryOnError(readableError(error));
    }
  }

  async function saveLook() {
    setTryOnError(null);
    try {
      await api.saveLook(withSelections(look, selections), tryOn?.result_ref ?? null);
      setSaved(true);
    } catch (error) {
      setTryOnError(readableError(error));
    }
  }

  function moveSelection(item: ItemResult, direction: -1 | 1) {
    if (!allowActions || rendering || item.products.length < 2) return;
    setSelections((current) => {
      const selected = current[item.item_id] ?? item.selected_index;
      const next = (selected + direction + item.products.length) % item.products.length;
      return { ...current, [item.item_id]: next };
    });
    setTryOn(null);
    setSaved(false);
  }

  return (
    <section className="results">
      <div className="result-lead">
        <img src={preview} alt={tryOn?.result_ref ? "Personalized outfit preview" : "Captured outfit"} />
        <div>
          <p className="eyebrow">{tryOn?.result_ref ? "On you" : "Closest"}</p>
          {total && (
            <strong>{formatPrice(total.minor, total.currency)}</strong>
          )}
          <button type="button" className="text-button" onClick={onPickAgain}>
            Pick another
          </button>
        </div>
      </div>
      {allowActions && (
        <div className="result-actions">
          <button
            type="button"
            className="primary"
            disabled={rendering}
            onClick={startTryOn}
          >
            {rendering
              ? tryOnStage(tryOn.stage)
              : tryOn?.status === "success"
                ? "Make it again"
                : "Try this look"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={saved || rendering}
            onClick={saveLook}
          >
            {saved ? "Saved" : "Save look"}
          </button>
        </div>
      )}
      {tryOnError && <p className="error">{tryOnError}</p>}
      <div className="product-list">
        {look.result.items.map((item) => {
          const garment = garments.get(item.item_id);
          const selected = selections[item.item_id] ?? item.selected_index;
          const product = item.products[selected];
          return (
            <section className="product-row" key={item.item_id}>
              <div className="product-row-heading">
                <strong>{garment?.category ?? "Original piece"}</strong>
                {item.products.length > 1 && (
                  <span>{selected + 1} / {item.products.length}</span>
                )}
              </div>
              {product ? (
                <div className="product-picker">
                  <button
                    type="button"
                    className="product-arrow"
                    aria-label={`Previous ${garment?.category ?? "product"}`}
                    disabled={!allowActions || rendering || item.products.length < 2}
                    onClick={() => moveSelection(item, -1)}
                  >
                    ←
                  </button>
                  <ProductCard
                    product={product}
                    inPreview={
                      tryOn?.rendered_garment_item_ids.includes(item.item_id) ?? false
                    }
                  />
                  <button
                    type="button"
                    className="product-arrow"
                    aria-label={`Next ${garment?.category ?? "product"}`}
                    disabled={!allowActions || rendering || item.products.length < 2}
                    onClick={() => moveSelection(item, 1)}
                  >
                    →
                  </button>
                </div>
              ) : (
                <article className="product-card unmatched-card">
                  <img src={mediaUrl(item.crop_ref)} alt="Unmatched original piece" />
                  <div>
                    <span className="utility">No close match found</span>
                    <strong>{garment?.category ?? "Original piece"}</strong>
                  </div>
                </article>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}

function SavedList({
  savedLooks,
  onOpen,
  onDelete,
  onClose,
}: {
  savedLooks: SavedLook[];
  onOpen: (saved: SavedLook) => void;
  onDelete: (savedId: string) => void;
  onClose: () => void;
}) {
  return (
    <section className="saved-list">
      <div className="section-heading">
        <div>
          <h2>Saved looks</h2>
        </div>
        <button type="button" className="text-button" onClick={onClose}>
          Close
        </button>
      </div>
      {savedLooks.length === 0 ? (
        <p className="empty-state">Nothing saved yet.</p>
      ) : (
        savedLooks.map((saved) => {
          const selectedProducts = productsFor(saved.snapshot.items, {});
          const total = productTotal(selectedProducts);
          return (
            <article className="saved-row" key={saved.id}>
              <button type="button" className="saved-open" onClick={() => onOpen(saved)}>
                <img
                  src={mediaUrl(saved.personalized_result_ref ?? saved.capture_ref)}
                  alt="Saved outfit"
                />
                <span>
                  {total && (
                    <strong>
                      {formatPrice(total.minor, total.currency)}
                    </strong>
                  )}
                  <small>{new Date(saved.created_at).toLocaleDateString()}</small>
                </span>
              </button>
              <button
                type="button"
                className="delete-button"
                aria-label="Delete saved look"
                onClick={() => onDelete(saved.id)}
              >
                ×
              </button>
            </article>
          );
        })
      )}
    </section>
  );
}

function ProductCard({
  product,
  inPreview,
}: {
  product: ProductMatch;
  inPreview: boolean;
}) {
  return (
    <a className="product-card" href={product.product_url} target="_blank" rel="noreferrer">
      <ProductImage key={product.image_url} product={product} />
      <div className="product-copy">
        <span className="utility">
          {inPreview ? "IN PREVIEW · " : ""}
          {product.match_kind === "exact" ? "EXACT" : "SIMILAR"}
        </span>
        <strong>{product.title}</strong>
        <span className="product-source">{product.retailer}</span>
        {product.price_minor !== null && product.currency !== null && (
          <span className="product-price">
            {formatPrice(product.price_minor, product.currency)}
          </span>
        )}
      </div>
      <span className="open-arrow" aria-hidden="true">
        ↗
      </span>
    </a>
  );
}

function ProductImage({ product }: { product: ProductMatch }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <span className="image-unavailable">Image unavailable</span>;
  }
  return (
    <img
      src={product.image_url}
      alt={product.title}
      onError={() => setFailed(true)}
    />
  );
}

function productsFor(
  items: ItemResult[],
  selections: Record<string, number>,
): ProductMatch[] {
  return items.flatMap((item) => {
    const product = item.products[selections[item.item_id] ?? item.selected_index];
    return product ? [product] : [];
  });
}

function withSelections(
  look: LookBuildResponse,
  selections: Record<string, number>,
): LookBuildResponse {
  return {
    ...look,
    result: {
      ...look.result,
      items: look.result.items.map((item) => ({
        ...item,
        selected_index: selections[item.item_id] ?? item.selected_index,
      })),
    },
  };
}

function productTotal(
  products: ProductMatch[],
): { minor: number; currency: string } | null {
  if (
    products.length === 0 ||
    products.some((product) => product.price_minor === null || product.currency === null)
  ) {
    return null;
  }
  const currencies = new Set(products.map((product) => product.currency));
  if (currencies.size !== 1) return null;
  return {
    minor: products.reduce((total, product) => total + (product.price_minor ?? 0), 0),
    currency: products[0].currency!,
  };
}

function formatPrice(minor: number, currency: string): string {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "INR" ? 0 : 2,
  }).format(minor / 100);
}

function tryOnStage(stage: string): string {
  if (stage === "applying_full_body") return "Putting on the outfit…";
  if (stage === "applying_upper_body") return "Putting on the top…";
  if (stage === "applying_lower_body") return "Putting on the bottom…";
  if (stage === "applying_shoes") return "Adding the shoes…";
  return "Making your preview…";
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Something stopped working";
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
