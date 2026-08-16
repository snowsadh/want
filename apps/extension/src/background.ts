import type { ExtensionMessage, PendingCapture } from "./types";

let pendingCapture: PendingCapture | null = null;

void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

chrome.runtime.onInstalled.addListener(() => {
  void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, sender, sendResponse: (response: unknown) => void) => {
    if (message.type === "GET_PENDING_CAPTURE") {
      sendResponse({ ok: true, capture: pendingCapture });
      return false;
    }
    if (message.type === "CLEAR_PENDING_CAPTURE") {
      pendingCapture = null;
      sendResponse({ ok: true });
      return false;
    }
    if (message.type === "START_CAPTURE") {
      void beginSelection().then(sendResponse).catch((error: unknown) => {
        sendResponse({ ok: false, error: readableError(error) });
      });
      return true;
    }
    if (message.type === "SELECTION_CONFIRMED") {
      void captureSelection(message, sender.tab)
        .then((capture) => {
          pendingCapture = capture;
          sendResponse({ ok: true });
          void chrome.runtime
            .sendMessage({ type: "CAPTURE_READY", capture } satisfies ExtensionMessage)
            .catch(() => undefined);
        })
        .catch((error: unknown) => {
          const message = readableError(error);
          sendResponse({ ok: false, error: message });
          void chrome.runtime
            .sendMessage({ type: "CAPTURE_FAILED", error: message } satisfies ExtensionMessage)
            .catch(() => undefined);
        });
      return true;
    }
    return false;
  },
);

async function beginSelection(): Promise<{ ok: true }> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.id) {
    throw new Error("No active page found");
  }
  await injectSelection(tab.id);
  return { ok: true };
}

async function injectSelection(tabId: number): Promise<void> {
  await chrome.scripting.executeScript({ target: { tabId }, files: ["assets/content.js"] });
  const response = (await chrome.tabs.sendMessage(tabId, { type: "BEGIN_SELECTION" })) as {
    ok?: boolean;
    error?: string;
  };
  if (!response?.ok) {
    throw new Error(response?.error ?? "Could not start selection on this page");
  }
}

async function captureSelection(
  message: Extract<ExtensionMessage, { type: "SELECTION_CONFIRMED" }>,
  tab: chrome.tabs.Tab | undefined,
): Promise<PendingCapture> {
  if (tab?.windowId === undefined) {
    throw new Error("The selected tab is no longer available");
  }
  const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, {
    format: "jpeg",
    quality: 92,
  });
  const pending: PendingCapture = {
    dataUrl,
    rect: message.rect,
    viewport: message.viewport,
    devicePixelRatio: message.devicePixelRatio,
    sourceImage: message.sourceImage,
    sourceVideo: message.sourceVideo,
    sourceUrl: tab.url ?? null,
    capturedAt: new Date().toISOString(),
  };
  return pending;
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown extension error";
}
