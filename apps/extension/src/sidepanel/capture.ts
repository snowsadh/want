import type { PendingCapture } from "../types";

export async function cropCapture(capture: PendingCapture): Promise<string> {
  if (capture.sourceVideo) {
    try {
      return await cropSourceVideo(capture);
    } catch {
      // Protected or cross-origin video frames fall through to the screenshot.
    }
  }
  if (capture.sourceImage) {
    try {
      return await cropSourceImage(capture);
    } catch {
      // Some sites block their original asset. The visible-tab capture remains reliable.
    }
  }
  const image = await loadImage(capture.dataUrl);
  const scaleX = image.naturalWidth / capture.viewport.width;
  const scaleY = image.naturalHeight / capture.viewport.height;
  const sourceX = Math.max(0, Math.round(capture.rect.x * scaleX));
  const sourceY = Math.max(0, Math.round(capture.rect.y * scaleY));
  const sourceWidth = Math.min(
    image.naturalWidth - sourceX,
    Math.max(1, Math.round(capture.rect.width * scaleX)),
  );
  const sourceHeight = Math.min(
    image.naturalHeight - sourceY,
    Math.max(1, Math.round(capture.rect.height * scaleY)),
  );
  const canvas = document.createElement("canvas");
  canvas.width = sourceWidth;
  canvas.height = sourceHeight;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Image cropping is unavailable");
  context.drawImage(
    image,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    0,
    0,
    sourceWidth,
    sourceHeight,
  );
  return canvas.toDataURL("image/jpeg", 0.92);
}

async function cropSourceVideo(capture: PendingCapture): Promise<string> {
  const source = capture.sourceVideo;
  if (!source) throw new Error("No video frame is available");
  const image = await loadImage(source.dataUrl);
  return cropRenderedSource(capture, image, source.renderedRect);
}

async function cropSourceImage(capture: PendingCapture): Promise<string> {
  const source = capture.sourceImage;
  if (!source) throw new Error("No page image is available");
  const response = await fetch(source.url, { credentials: "omit" });
  if (!response.ok) throw new Error("The page image could not be downloaded");
  const objectUrl = URL.createObjectURL(await response.blob());
  try {
    const image = await loadImage(objectUrl);
    return cropRenderedSource(capture, image, source.renderedRect);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function cropRenderedSource(
  capture: PendingCapture,
  image: HTMLImageElement,
  renderedRect: PendingCapture["rect"],
): string {
  const left = Math.max(capture.rect.x, renderedRect.x);
  const top = Math.max(capture.rect.y, renderedRect.y);
  const right = Math.min(capture.rect.x + capture.rect.width, renderedRect.x + renderedRect.width);
  const bottom = Math.min(
    capture.rect.y + capture.rect.height,
    renderedRect.y + renderedRect.height,
  );
  if (right <= left || bottom <= top) throw new Error("The selection missed the source visual");
  const scaleX = image.naturalWidth / renderedRect.width;
  const scaleY = image.naturalHeight / renderedRect.height;
  return drawCrop(
    image,
    Math.round((left - renderedRect.x) * scaleX),
    Math.round((top - renderedRect.y) * scaleY),
    Math.round((right - left) * scaleX),
    Math.round((bottom - top) * scaleY),
  );
}

function drawCrop(
  image: HTMLImageElement,
  sourceX: number,
  sourceY: number,
  sourceWidth: number,
  sourceHeight: number,
): string {
  const width = Math.min(image.naturalWidth - sourceX, Math.max(1, sourceWidth));
  const height = Math.min(image.naturalHeight - sourceY, Math.max(1, sourceHeight));
  const scale = Math.min(1, 2048 / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Image cropping is unavailable");
  context.drawImage(image, sourceX, sourceY, width, height, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.95);
}

function loadImage(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("The captured image could not be opened"));
    image.src = source;
  });
}
