declare global {
  interface Window {
    __wantCaptureLoaded?: boolean;
  }
}

if (!window.__wantCaptureLoaded) {
  window.__wantCaptureLoaded = true;
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "BEGIN_SELECTION") return false;
    if (document.querySelector("want-capture-overlay")) {
      sendResponse({ ok: false, error: "A selection is already open" });
      return false;
    }
    mountSelectionOverlay();
    sendResponse({ ok: true });
    return false;
  });
}

function mountSelectionOverlay(): void {
  const host = document.createElement("want-capture-overlay");
  const shadow = host.attachShadow({ mode: "closed" });
  const surface = document.createElement("div");
  const selection = document.createElement("div");
  const hint = document.createElement("div");
  const actions = document.createElement("div");
  const confirm = document.createElement("button");
  const cancel = document.createElement("button");
  surface.className = "surface";
  selection.className = "selection";
  hint.className = "hint";
  actions.className = "actions";
  confirm.className = "confirm";
  cancel.className = "cancel";
  hint.textContent = "Drag around the look";
  confirm.textContent = "Use this";
  cancel.textContent = "Cancel";
  actions.append(cancel, confirm);
  selection.append(actions);
  surface.append(hint, selection);
  shadow.append(styleElement(), surface);
  document.documentElement.append(host);

  let startX = 0;
  let startY = 0;
  let rect = { x: 0, y: 0, width: 0, height: 0 };
  let drawing = false;

  surface.addEventListener("pointerdown", (event) => {
    if (event.target instanceof HTMLButtonElement) return;
    drawing = true;
    startX = event.clientX;
    startY = event.clientY;
    selection.classList.add("active");
    actions.classList.remove("visible");
    hint.classList.add("hidden");
    surface.setPointerCapture(event.pointerId);
    update(event.clientX, event.clientY);
  });
  surface.addEventListener("pointermove", (event) => {
    if (drawing) update(event.clientX, event.clientY);
  });
  surface.addEventListener("pointerup", (event) => {
    if (!drawing) return;
    drawing = false;
    surface.releasePointerCapture(event.pointerId);
    update(event.clientX, event.clientY);
    if (rect.width < 32 || rect.height < 32) {
      selection.classList.remove("active");
      hint.textContent = "Make the box a little bigger";
      hint.classList.remove("hidden");
      return;
    }
    actions.classList.add("visible");
  });
  cancel.addEventListener("click", () => cleanup());
  confirm.addEventListener("click", () => {
    const payload = {
      type: "SELECTION_CONFIRMED",
      rect,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      devicePixelRatio: window.devicePixelRatio,
      sourceImage: findSourceImage(rect),
      sourceVideo: captureSourceVideo(rect),
    };
    hideCursorForCapture();
    cleanup();
    window.setTimeout(() => void chrome.runtime.sendMessage(payload), 80);
  });
  window.addEventListener("keydown", onKeydown, { capture: true });

  function update(currentX: number, currentY: number): void {
    const x = Math.max(0, Math.min(startX, currentX));
    const y = Math.max(0, Math.min(startY, currentY));
    const right = Math.min(window.innerWidth, Math.max(startX, currentX));
    const bottom = Math.min(window.innerHeight, Math.max(startY, currentY));
    rect = { x, y, width: right - x, height: bottom - y };
    Object.assign(selection.style, {
      left: `${rect.x}px`,
      top: `${rect.y}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
    });
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === "Escape") cleanup();
  }

  function cleanup(): void {
    window.removeEventListener("keydown", onKeydown, { capture: true });
    host.remove();
  }
}

function hideCursorForCapture(): void {
  const style = document.createElement("style");
  style.textContent = "*, *::before, *::after { cursor: none !important; }";
  document.documentElement.append(style);
  window.setTimeout(() => style.remove(), 750);
}

function findSourceImage(selection: { x: number; y: number; width: number; height: number }) {
  const selectionArea = selection.width * selection.height;
  if (selectionArea <= 0) return undefined;

  const matches = [...document.images]
    .map((image) => {
      const bounds = image.getBoundingClientRect();
      const left = Math.max(selection.x, bounds.left);
      const top = Math.max(selection.y, bounds.top);
      const right = Math.min(selection.x + selection.width, bounds.right);
      const bottom = Math.min(selection.y + selection.height, bounds.bottom);
      const overlap = Math.max(0, right - left) * Math.max(0, bottom - top);
      const renderedRatio = bounds.width / Math.max(1, bounds.height);
      const naturalRatio = image.naturalWidth / Math.max(1, image.naturalHeight);
      const ratioError = Math.abs(renderedRatio / naturalRatio - 1);
      return { image, bounds, coverage: overlap / selectionArea, ratioError };
    })
    .filter(
      ({ image, bounds, coverage, ratioError }) =>
        coverage >= 0.65 &&
        ratioError <= 0.04 &&
        bounds.width >= 32 &&
        bounds.height >= 32 &&
        image.naturalWidth >= 64 &&
        image.naturalHeight >= 64 &&
        Boolean(image.currentSrc || image.src),
    )
    .sort((a, b) => b.coverage - a.coverage);

  const best = matches[0];
  if (!best) return undefined;
  return {
    url: best.image.currentSrc || best.image.src,
    renderedRect: {
      x: best.bounds.left,
      y: best.bounds.top,
      width: best.bounds.width,
      height: best.bounds.height,
    },
    naturalWidth: best.image.naturalWidth,
    naturalHeight: best.image.naturalHeight,
  };
}

function captureSourceVideo(selection: {
  x: number;
  y: number;
  width: number;
  height: number;
}) {
  const selectionArea = selection.width * selection.height;
  if (selectionArea <= 0) return undefined;
  const matches = [...document.querySelectorAll("video")]
    .map((video) => {
      const bounds = video.getBoundingClientRect();
      const left = Math.max(selection.x, bounds.left);
      const top = Math.max(selection.y, bounds.top);
      const right = Math.min(selection.x + selection.width, bounds.right);
      const bottom = Math.min(selection.y + selection.height, bounds.bottom);
      const overlap = Math.max(0, right - left) * Math.max(0, bottom - top);
      return { video, bounds, coverage: overlap / selectionArea };
    })
    .filter(
      ({ video, bounds, coverage }) =>
        coverage >= 0.65 &&
        bounds.width >= 32 &&
        bounds.height >= 32 &&
        video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
        video.videoWidth >= 64 &&
        video.videoHeight >= 64,
    )
    .sort((a, b) => b.coverage - a.coverage);
  const best = matches[0];
  if (!best) return undefined;

  try {
    const maxSide = 2048;
    const scale = Math.min(1, maxSide / Math.max(best.video.videoWidth, best.video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(best.video.videoWidth * scale));
    canvas.height = Math.max(1, Math.round(best.video.videoHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) return undefined;
    context.drawImage(best.video, 0, 0, canvas.width, canvas.height);
    return {
      dataUrl: canvas.toDataURL("image/jpeg", 0.94),
      renderedRect: {
        x: best.bounds.left,
        y: best.bounds.top,
        width: best.bounds.width,
        height: best.bounds.height,
      },
      naturalWidth: canvas.width,
      naturalHeight: canvas.height,
    };
  } catch {
    // Cross-origin video frames can taint canvas; visible-tab capture remains the fallback.
    return undefined;
  }
}

function styleElement(): HTMLStyleElement {
  const style = document.createElement("style");
  style.textContent = `
    :host { all: initial; }
    .surface { position: fixed; inset: 0; z-index: 2147483647; cursor: crosshair; font-family: Arial, sans-serif; }
    .hint { position: fixed; top: 20px; left: 50%; translate: -50% 0; color: #17191c; background: #f7f8fc; border: 2px solid #17191c; padding: 9px 13px; font: 700 13px/1 Arial, sans-serif; box-shadow: 4px 4px 0 #315cff; }
    .hint.hidden { display: none; }
    .selection { position: fixed; display: none; border: 3px solid #315cff; box-sizing: border-box; box-shadow: 0 0 0 9999px rgb(13 16 24 / 48%); }
    .selection::before, .selection::after { content: ""; position: absolute; width: 20px; height: 20px; border-color: #ff4f70; }
    .selection::before { left: -6px; top: -6px; border-left: 6px solid #ff4f70; border-top: 6px solid #ff4f70; }
    .selection::after { right: -6px; bottom: -6px; border-right: 6px solid #ff4f70; border-bottom: 6px solid #ff4f70; }
    .selection.active { display: block; }
    .actions { position: absolute; right: -3px; bottom: -48px; display: none; gap: 7px; cursor: default; }
    .actions.visible { display: flex; }
    button { border: 2px solid #17191c; padding: 9px 12px; font: 700 12px/1 Arial, sans-serif; cursor: pointer; }
    .confirm { color: #fff; background: #315cff; }
    .cancel { color: #17191c; background: #f7f8fc; }
  `;
  return style;
}

export {};
