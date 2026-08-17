import assert from "node:assert/strict";

let actionListener;
let messageListener;
const calls = { opened: 0, injected: [], sent: [] };

globalThis.chrome = {
  action: {
    onClicked: { addListener: (listener) => { actionListener = listener; } },
  },
  sidebarAction: {
    open: async () => { calls.opened += 1; },
  },
  runtime: {
    onMessage: { addListener: (listener) => { messageListener = listener; } },
    sendMessage: async (message) => { calls.sent.push(message); },
  },
  scripting: {
    executeScript: async (details) => { calls.injected.push(details); },
  },
  tabs: {
    query: async () => [{ id: 7 }],
    sendMessage: async () => ({ ok: true }),
    captureVisibleTab: async () => "data:image/jpeg;base64,dGVzdA==",
  },
};

await import("../dist/assets/background.js");
assert.equal(typeof actionListener, "function");
assert.equal(typeof messageListener, "function");

await actionListener();
assert.equal(calls.opened, 1);

let response;
assert.equal(messageListener({ type: "START_CAPTURE" }, {}, (value) => { response = value; }), true);
await new Promise(setImmediate);
assert.deepEqual(response, { ok: true });
assert.deepEqual(calls.injected, [{ target: { tabId: 7 }, files: ["assets/content.js"] }]);

const selection = {
  type: "SELECTION_CONFIRMED",
  rect: { x: 10, y: 20, width: 100, height: 200 },
  viewport: { width: 1280, height: 720 },
  devicePixelRatio: 1,
};
assert.equal(
  messageListener(selection, { tab: { windowId: 3, url: "https://example.com/look" } }, (value) => { response = value; }),
  true,
);
await new Promise(setImmediate);
assert.deepEqual(response, { ok: true });
assert.equal(calls.sent.at(-1).type, "CAPTURE_READY");
assert.equal(calls.sent.at(-1).capture.sourceUrl, "https://example.com/look");

messageListener({ type: "GET_PENDING_CAPTURE" }, {}, (value) => { response = value; });
assert.equal(response.capture.sourceUrl, "https://example.com/look");

console.log("Firefox background/sidebar/capture build check passed");
