import "@fontsource-variable/archivo";
import "@fontsource-variable/manrope";
import "@fontsource/space-mono/400.css";
import {
  StrictMode,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
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
  UserProfile,
} from "../types";
import { cropCapture } from "./capture";
import "./styles.css";

type Connection = "checking" | "online" | "offline";
type View = "home" | "me";

function App() {
  const [connection, setConnection] = useState<Connection>("checking");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [onboardingStep, setOnboardingStep] = useState<number | null>(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready when you are");
  const [error, setError] = useState<string | null>(null);
  const [capture, setCapture] = useState<{ preview: string; sourceUrl: string | null } | null>(null);
  const [look, setLook] = useState<LookBuildResponse | null>(null);
  const [savedLooks, setSavedLooks] = useState<SavedLook[]>([]);
  const [view, setView] = useState<View>("home");
  const [viewingSaved, setViewingSaved] = useState(false);
  const uploadInput = useRef<HTMLInputElement>(null);
  const lastCaptureAt = useRef<string | null>(null);

  const resetHome = useCallback(() => {
    setView("home");
    setCapture(null);
    setLook(null);
    setViewingSaved(false);
    setError(null);
    setStatus("Ready when you are");
  }, []);

  const consumeCapture = useCallback(async (pending: PendingCapture) => {
    if (lastCaptureAt.current === pending.capturedAt) return;
    lastCaptureAt.current = pending.capturedAt;
    try {
      const preview = await cropCapture(pending);
      setCapture({ preview, sourceUrl: pending.sourceUrl });
      setLook(null);
      setView("home");
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
        setProfile(currentProfile);
        if (!currentProfile) setOnboardingStep(0);
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
      setError("Choose a clear, full-body photo first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const currentProfile = await api.uploadPhoto(photo);
      setProfile(currentProfile);
      setSetupOpen(false);
      setOnboardingStep(null);
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
      if (!response?.ok) throw new Error(response?.error ?? "Could not start capture on this page");
    } catch (captureError) {
      const message = readableError(captureError);
      setError(message.includes("Cannot access contents") ? "Chrome blocks capture on this page. Try a regular website." : message);
      setStatus("Capture stopped");
    }
  }

  function uploadLook(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Choose a JPEG, PNG, or WebP image");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("That image is larger than 10 MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setCapture({ preview: String(reader.result), sourceUrl: null });
      setLook(null);
      setView("home");
      setViewingSaved(false);
      setError(null);
      setStatus("Image ready");
    };
    reader.onerror = () => setError("That image could not be opened");
    reader.readAsDataURL(file);
  }

  async function findPieces() {
    if (!capture) return;
    setBusy(true);
    setError(null);
    setStatus("Reading the clothes and searching stores…");
    try {
      setLook(await api.createLook(capture.preview, capture.sourceUrl));
      setStatus("Closest outfit ready");
    } catch (lookError) {
      setError(readableError(lookError));
      setStatus("Search stopped");
    } finally {
      setBusy(false);
    }
  }

  async function openMe() {
    setError(null);
    setView("me");
    setCapture(null);
    setLook(null);
    setViewingSaved(false);
    try {
      setSavedLooks(await api.savedLooks());
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
    setView("home");
  }

  async function deleteSavedLook(savedId: string) {
    try {
      await api.deleteSavedLook(savedId);
      setSavedLooks((current) => current.filter((saved) => saved.id !== savedId));
    } catch (deleteError) {
      setError(readableError(deleteError));
    }
  }

  if (onboardingStep !== null && !setupOpen) {
    return (
      <Shell>
        <Onboarding
          step={onboardingStep}
          onBack={() => setOnboardingStep((current) => Math.max(0, (current ?? 0) - 1))}
          onNext={() => {
            if (onboardingStep === 2) {
              setOnboardingStep(null);
              setSetupOpen(true);
            } else {
              setOnboardingStep(onboardingStep + 1);
            }
          }}
        />
      </Shell>
    );
  }

  if (setupOpen) {
    return (
      <Shell>
        <SetupPhoto
          photo={photo}
          busy={busy}
          connection={connection}
          error={error}
          onPhoto={setPhoto}
          onSave={saveSetup}
          onClose={profile ? () => setSetupOpen(false) : undefined}
        />
      </Shell>
    );
  }

  return (
    <Shell view={view} profile={profile} onHome={resetHome} onMe={openMe}>
      <input ref={uploadInput} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={uploadLook} />
      {view === "me" ? (
        <MeView
          profile={profile}
          savedLooks={savedLooks}
          onOpen={openSavedLook}
          onDelete={deleteSavedLook}
          onChangePhoto={() => setSetupOpen(true)}
          error={error}
        />
      ) : (
        <main className="home">
          {busy && capture && !look ? (
            <DiscoveryProcessing preview={capture.preview} />
          ) : capture && !look ? (
            <CaptureReady
              preview={capture.preview}
              onFind={findPieces}
              onPickAgain={resetHome}
            />
          ) : look && capture ? (
            <LookView
              look={look}
              capturePreview={capture.preview}
              onPickAgain={resetHome}
              onHome={resetHome}
              allowActions={!viewingSaved}
              savedView={viewingSaved}
            />
          ) : (
            <Launcher
              onCapture={startCapture}
              onUpload={() => uploadInput.current?.click()}
              onMe={openMe}
            />
          )}
          {(error || (!look && !capture)) && (
            <div className={`status-line ${error ? "has-error" : ""}`}>
              <span className={`status-dot ${connection}`} />
              <span>{error ?? status}</span>
            </div>
          )}
        </main>
      )}
    </Shell>
  );
}

const onboardingSlides = [
  {
    image: "/onboarding/grab.png",
    number: "01",
    title: "Grab a look from anywhere.",
    copy: "Box it on any page, or upload a screenshot you already love.",
  },
  {
    image: "/onboarding/try.png",
    number: "02",
    title: "Try it on yourself.",
    copy: "WANT! finds the pieces. YouCam shows the supported outfit on you.",
  },
  {
    image: "/onboarding/get.png",
    number: "03",
    title: "Get the real pieces.",
    copy: "Every matched item opens the retailer—no mystery products, no dead ends.",
  },
];

function Onboarding({ step, onBack, onNext }: { step: number; onBack: () => void; onNext: () => void }) {
  const slide = onboardingSlides[step];
  return (
    <main className="onboarding">
      <div className="onboarding-visual">
        <img src={slide.image} alt="" />
        <span className="slide-number">{slide.number}</span>
      </div>
      <div className="onboarding-copy">
        <p className="eyebrow">How WANT! works</p>
        <h1>{slide.title}</h1>
        <p className="lede">{slide.copy}</p>
      </div>
      <div className="onboarding-footer">
        <div className="pagination" aria-label={`Step ${step + 1} of 3`}>
          {onboardingSlides.map((item, index) => <span key={item.number} className={index === step ? "active" : ""} />)}
        </div>
        <div className="onboarding-actions">
          {step > 0 && <button type="button" className="quiet-button" onClick={onBack}>Back</button>}
          <button type="button" className="primary compact" onClick={onNext}>{step === 2 ? "Set up my photo" : "Next"}</button>
        </div>
      </div>
    </main>
  );
}

function SetupPhoto({
  photo,
  busy,
  connection,
  error,
  onPhoto,
  onSave,
  onClose,
}: {
  photo: File | null;
  busy: boolean;
  connection: Connection;
  error: string | null;
  onPhoto: (file: File | null) => void;
  onSave: () => void;
  onClose?: () => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!photo) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);
  return (
    <main className="setup">
      <div className="section-topline">
        <p className="eyebrow">Your fitting-room photo</p>
        {onClose && <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>×</button>}
      </div>
      <h1>One photo.<br />Every look.</h1>
      <p className="lede">Use a clear, front-facing photo where your full outfit area is visible.</p>
      <label className={`photo-drop ${preview ? "has-preview" : ""}`}>
        <input type="file" accept="image/jpeg,image/png" onChange={(event) => onPhoto(event.target.files?.[0] ?? null)} />
        {preview ? <img src={preview} alt="Your selected photo" /> : <UploadMark />}
        <span className="photo-drop-copy">
          <strong>{photo ? "Choose a different photo" : "Choose your photo"}</strong>
          <span>JPEG or PNG · 10 MB max</span>
        </span>
      </label>
      <div className="privacy-note"><LockIcon /><span>Stored privately for your try-ons.</span></div>
      {error && <p className="error">{error}</p>}
      <button className="primary" type="button" disabled={busy || connection !== "online"} onClick={onSave}>
        {busy ? "Saving…" : connection === "offline" ? "Service unavailable" : "Save and continue"}
      </button>
    </main>
  );
}

function Shell({
  children,
  view,
  profile,
  onHome,
  onMe,
}: {
  children: ReactNode;
  view?: View;
  profile?: UserProfile | null;
  onHome?: () => void;
  onMe?: () => void;
}) {
  return (
    <div className="app-shell">
      <header>
        <button type="button" className="wordmark" onClick={onHome} disabled={!onHome}>WANT!</button>
        {onHome && onMe && (
          <nav aria-label="Main navigation">
            <button type="button" className={view === "home" ? "active" : ""} onClick={onHome}>Home</button>
            <button type="button" className={`avatar-button ${view === "me" ? "active" : ""}`} aria-label="Me" onClick={onMe}>
              {profile ? <img src={mediaUrl(profile.photo_ref)} alt="" /> : "Me"}
            </button>
          </nav>
        )}
      </header>
      {children}
    </div>
  );
}

function Launcher({ onCapture, onUpload, onMe }: { onCapture: () => void; onUpload: () => void; onMe: () => void }) {
  return (
    <section className="launcher">
      <div className="home-intro">
        <p className="eyebrow">Your visual fitting room</p>
        <h1>Wear what<br />caught your eye.</h1>
        <p className="lede">Pick a look from anywhere. We’ll find the real pieces and put the supported outfit on you.</p>
      </div>
      <button className="launch-card featured" type="button" onClick={onCapture}>
        <span className="launch-icon"><FrameIcon /></span>
        <span><strong>Capture this page</strong><small>Drag a box around any look</small></span>
        <kbd>Alt W</kbd>
      </button>
      <div className="launch-grid">
        <button className="launch-card" type="button" onClick={onUpload}>
          <span className="launch-icon"><UploadIcon /></span>
          <span><strong>Upload image</strong><small>From your device</small></span>
        </button>
        <button className="launch-card" type="button" onClick={onMe}>
          <span className="launch-icon"><HeartIcon /></span>
          <span><strong>My looks</strong><small>Saved on this device</small></span>
        </button>
      </div>
      <p className="launcher-footnote"><SparkIcon /> Powered by YouCam virtual try-on</p>
    </section>
  );
}

function CaptureReady({ preview, onFind, onPickAgain }: { preview: string; onFind: () => void; onPickAgain: () => void }) {
  return (
    <section className="capture-ready">
      <div className="section-topline">
        <p className="eyebrow">Your reference look</p>
        <button type="button" className="quiet-button" onClick={onPickAgain}>Replace</button>
      </div>
      <div className="capture-frame"><img src={preview} alt="Selected look" /><span className="scan-corner tl" /><span className="scan-corner br" /></div>
      <div className="ready-note"><span className="ready-dot" /><span>Ready to find each visible piece</span></div>
      <button className="primary want-button" type="button" onClick={onFind}>WANT! this look <span>→</span></button>
    </section>
  );
}

const discoveryTips = [
  "Reading every visible piece",
  "Searching each item at the same time",
  "Keeping only real retailer links",
  "No close match? We keep the original",
];

function DiscoveryProcessing({ preview }: { preview: string }) {
  const [tip, setTip] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setTip((current) => (current + 1) % discoveryTips.length), 2800);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <section className="processing-view" aria-live="polite">
      <div className="processing-image">
        <img src={preview} alt="Your selected look" />
        <div className="scan-line" />
        <span className="scan-label">Understanding look</span>
      </div>
      <div className="processing-copy">
        <p className="eyebrow">Building your closest outfit</p>
        <h2>Good taste.<br />Give us a moment.</h2>
        <div className="thread-loader"><span /><span /><span /></div>
        <p className="tip" key={tip}><span>Tip {String(tip + 1).padStart(2, "0")}</span>{discoveryTips[tip]}</p>
      </div>
    </section>
  );
}

function LookView({
  look,
  capturePreview,
  onPickAgain,
  onHome,
  allowActions,
  savedView,
}: {
  look: LookBuildResponse;
  capturePreview: string;
  onPickAgain: () => void;
  onHome: () => void;
  allowActions: boolean;
  savedView: boolean;
}) {
  const [tryOn, setTryOn] = useState<TryOnJob | null>(null);
  const [tryOnError, setTryOnError] = useState<string | null>(null);
  const [saved, setSaved] = useState(savedView);
  const [selections, setSelections] = useState<Record<string, number>>(() =>
    Object.fromEntries(look.result.items.map((item) => [item.item_id, item.selected_index])),
  );
  const garments = new Map(look.result.analysis.garments.map((garment) => [garment.item_id, garment]));
  const selectedProducts = productsFor(look.result.items, selections);
  const total = productTotal(selectedProducts);
  const rendering = tryOn?.status === "queued" || tryOn?.status === "running";
  const showTryView = savedView || tryOn?.status === "success";

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

  function chooseSelection(item: ItemResult, selected: number) {
    if (!allowActions || rendering) return;
    setSelections((current) => ({ ...current, [item.item_id]: selected }));
    setTryOn(null);
    setSaved(false);
  }

  if (rendering) {
    return <TryOnProcessing preview={capturePreview} stage={tryOn.stage} />;
  }

  if (showTryView) {
    return (
      <TryResult
        image={savedView ? capturePreview : mediaUrl(tryOn!.result_ref!)}
        look={look}
        selections={selections}
        renderedIds={new Set(tryOn?.rendered_garment_item_ids ?? [])}
        savedView={savedView}
        saved={saved}
        onSave={saveLook}
        onTryAnother={() => setTryOn(null)}
        onHome={onHome}
      />
    );
  }

  return (
    <section className="results">
      <div className="result-heading">
        <div>
          <p className="eyebrow">Closest outfit</p>
          <h2>Built from the look.</h2>
        </div>
        <button type="button" className="quiet-button" onClick={onPickAgain}>Start over</button>
      </div>
      <div className="reference-strip">
        <img src={capturePreview} alt="Your reference outfit" />
        <div><span>Reference</span><strong>{look.result.items.length} pieces found</strong></div>
        {total && <span className="look-total">{formatPrice(total.minor, total.currency)}</span>}
      </div>
      <div className="product-list">
        {look.result.items.map((item) => {
          const garment = garments.get(item.item_id);
          const selected = selections[item.item_id] ?? item.selected_index;
          const product = item.products[selected];
          return (
            <section className="product-row" key={item.item_id}>
              <div className="product-row-heading">
                <strong>{garment?.category ?? "Original piece"}</strong>
              </div>
              {product ? (
                <ProductOptions
                  products={item.products}
                  selected={selected}
                  disabled={!allowActions}
                  onSelect={(index) => chooseSelection(item, index)}
                />
              ) : (
                <article className="product-card unmatched-card">
                  <img src={mediaUrl(item.crop_ref)} alt="Unmatched original piece" />
                  <div><span className="utility">Reference only</span><strong>{garment?.category ?? "Original piece"}</strong><small>No honest match found</small></div>
                </article>
              )}
            </section>
          );
        })}
      </div>
      {tryOnError && <p className="error">{tryOnError}</p>}
      {allowActions && (
        <div className="sticky-actions">
          <div>{total ? <><span>Selected total</span><strong>{formatPrice(total.minor, total.currency)}</strong></> : <span>Prices shown per item</span>}</div>
          <button type="button" className="primary compact" onClick={startTryOn}>Try it on <span>→</span></button>
        </div>
      )}
    </section>
  );
}

function TryOnProcessing({ preview, stage }: { preview: string; stage: string }) {
  return (
    <section className="try-processing" aria-live="polite">
      <div className="try-processing-image"><img src={preview} alt="Your fitting-room photo" /><div className="render-glow" /></div>
      <p className="eyebrow">YouCam virtual try-on</p>
      <h2>{tryOnStage(stage)}</h2>
      <p>Keep this panel open. We’re fitting the supported garments to your photo.</p>
      <div className="render-progress"><span /></div>
    </section>
  );
}

function TryResult({
  image,
  look,
  selections,
  renderedIds,
  savedView,
  saved,
  onSave,
  onTryAnother,
  onHome,
}: {
  image: string;
  look: LookBuildResponse;
  selections: Record<string, number>;
  renderedIds: Set<string>;
  savedView: boolean;
  saved: boolean;
  onSave: () => void;
  onTryAnother: () => void;
  onHome: () => void;
}) {
  const selected = look.result.items.flatMap((item) => {
    const product = item.products[selections[item.item_id] ?? item.selected_index];
    return product ? [{ itemId: item.item_id, product }] : [];
  });
  return (
    <section className="try-result">
      <div className="try-result-topline">
        <div><p className="eyebrow">{savedView ? "Saved look" : "On you"}</p><h2>{savedView ? "Worth another look." : "There you are."}</h2></div>
        {!savedView && <button type="button" className={`heart-button ${saved ? "saved" : ""}`} aria-label={saved ? "Saved" : "Save look"} disabled={saved} onClick={onSave}><HeartIcon filled={saved} /></button>}
      </div>
      <div className="try-hero"><img src={image} alt={savedView ? "Your saved look" : "You wearing the selected outfit"} /><span className="youcam-mark">Rendered with YouCam</span></div>
      <div className="worn-heading"><strong>Pieces in this look</strong><span>Open any item at its store</span></div>
      <div className="worn-tray">
        {selected.map(({ itemId, product }) => (
          <MiniProduct key={itemId} product={product} label={!savedView && !renderedIds.has(itemId) ? "Not in preview" : undefined} />
        ))}
      </div>
      <div className="try-actions">
        {!savedView && <button type="button" className="primary" onClick={onTryAnother}>Try another combo</button>}
        <button type="button" className="quiet-button centered" onClick={onHome}>Back home</button>
      </div>
    </section>
  );
}

function ProductOptions({
  products,
  selected,
  disabled,
  onSelect,
}: {
  products: ProductMatch[];
  selected: number;
  disabled: boolean;
  onSelect: (index: number) => void;
}) {
  const chosen = products[selected];
  return (
    <div className="product-options">
      <div className="option-rail">
        {products.map((product, index) => {
          let position = index - selected;
          if (products.length === 3 && position > 1) position -= 3;
          if (products.length === 3 && position < -1) position += 3;
          return (
          <article
            className={`option-tile ${index === selected ? "selected" : ""}`}
            key={`${product.product_url}-${index}`}
            style={{
              "--offset": `${position * 104}px`,
              "--tilt": `${position * -3}deg`,
            } as CSSProperties}
          >
            <button
              type="button"
              className="option-product"
              aria-label={`Select ${product.title}`}
              aria-pressed={index === selected}
              disabled={disabled}
              onClick={() => onSelect(index)}
            >
              <ProductImage key={product.image_url} product={product} />
            </button>
          </article>
          );
        })}
      </div>
      <a className="option-summary" href={chosen.product_url} target="_blank" rel="noreferrer">
        <span>{chosen.retailer}</span>
        <strong>{chosen.price_minor !== null && chosen.currency !== null ? `${formatPrice(chosen.price_minor, chosen.currency)} ` : ""}↗</strong>
      </a>
    </div>
  );
}

function MiniProduct({ product, label }: { product: ProductMatch; label?: string }) {
  return (
    <a className="mini-product" href={product.product_url} target="_blank" rel="noreferrer">
      <div className="product-image-wrap"><ProductImage product={product} /><span className="get-overlay" aria-hidden="true">↗</span></div>
      {label && <span className="shop-only">{label}</span>}
      <strong>{product.title}</strong>
      {product.price_minor !== null && product.currency !== null && <span>{formatPrice(product.price_minor, product.currency)}</span>}
    </a>
  );
}

function ProductImage({ product }: { product: ProductMatch }) {
  const [failed, setFailed] = useState(false);
  return failed ? <span className="image-unavailable">Image unavailable</span> : <img src={product.image_url} alt={product.title} onError={() => setFailed(true)} />;
}

function MeView({
  profile,
  savedLooks,
  onOpen,
  onDelete,
  onChangePhoto,
  error,
}: {
  profile: UserProfile | null;
  savedLooks: SavedLook[];
  onOpen: (saved: SavedLook) => void;
  onDelete: (savedId: string) => void;
  onChangePhoto: () => void;
  error: string | null;
}) {
  return (
    <main className="me-view">
      <div className="profile-card">
        {profile && <img src={mediaUrl(profile.photo_ref)} alt="Your fitting-room photo" />}
        <div><p className="eyebrow">Your fitting room</p><h1>Me.</h1><p>Saved privately on this device.</p><button type="button" className="quiet-button" onClick={onChangePhoto}>Change photo</button></div>
      </div>
      <div className="saved-heading"><div><p className="eyebrow">The wardrobe</p><h2>Saved looks</h2></div><span>{savedLooks.length}</span></div>
      {error && <p className="error">{error}</p>}
      {savedLooks.length === 0 ? (
        <div className="empty-state"><HeartIcon /><strong>Your wardrobe is waiting.</strong><p>Looks you save after trying them on will live here.</p></div>
      ) : (
        <div className="saved-grid">
          {savedLooks.map((saved) => {
            const total = productTotal(productsFor(saved.snapshot.items, {}));
            return (
              <article className="saved-tile" key={saved.id}>
                <button type="button" className="saved-open" onClick={() => onOpen(saved)}>
                  <img src={mediaUrl(saved.personalized_result_ref ?? saved.capture_ref)} alt="Saved outfit" />
                  <span><strong>{new Date(saved.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</strong>{total && <small>{formatPrice(total.minor, total.currency)}</small>}</span>
                </button>
                <button type="button" className="delete-button" aria-label="Delete saved look" onClick={() => onDelete(saved.id)}>×</button>
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}

function FrameIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" /></svg>; }
function UploadIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0L7 9m5-5 5 5M4 15v5h16v-5" /></svg>; }
function HeartIcon({ filled = false }: { filled?: boolean }) { return <svg viewBox="0 0 24 24" aria-hidden="true" className={filled ? "filled" : ""}><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.7-7.5 1.1-1.1a5.5 5.5 0 0 0 0-7.8Z" /></svg>; }
function SparkIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c0 6-4 10-10 10 6 0 10 4 10 10 0-6 4-10 10-10-6 0-10-4-10-10Z" /></svg>; }
function LockIcon() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 10h12v10H6zM8.5 10V7a3.5 3.5 0 0 1 7 0v3" /></svg>; }
function UploadMark() { return <span className="upload-mark"><UploadIcon /></span>; }

function productsFor(items: ItemResult[], selections: Record<string, number>): ProductMatch[] {
  return items.flatMap((item) => {
    const product = item.products[selections[item.item_id] ?? item.selected_index];
    return product ? [product] : [];
  });
}

function withSelections(look: LookBuildResponse, selections: Record<string, number>): LookBuildResponse {
  return { ...look, result: { ...look.result, items: look.result.items.map((item) => ({ ...item, selected_index: selections[item.item_id] ?? item.selected_index })) } };
}

function productTotal(products: ProductMatch[]): { minor: number; currency: string } | null {
  if (products.length === 0 || products.some((product) => product.price_minor === null || product.currency === null)) return null;
  const currencies = new Set(products.map((product) => product.currency));
  if (currencies.size !== 1) return null;
  return { minor: products.reduce((total, product) => total + (product.price_minor ?? 0), 0), currency: products[0].currency! };
}

function formatPrice(minor: number, currency: string): string {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : undefined, { style: "currency", currency, maximumFractionDigits: currency === "INR" ? 0 : 2 }).format(minor / 100);
}

function tryOnStage(stage: string): string {
  if (stage === "applying_full_body") return "Putting on the outfit…";
  if (stage === "applying_upper_body") return "Fitting the top…";
  if (stage === "applying_lower_body") return "Fitting the bottom…";
  if (stage === "applying_shoes") return "Adding the shoes…";
  return "Making your preview…";
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Something stopped working";
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
