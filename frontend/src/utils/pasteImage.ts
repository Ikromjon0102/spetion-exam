import type { ClipboardEvent } from "react";

/** A teacher takes a screenshot (e.g. a Snipping Tool crop of a complex
 * formula), which most OS screenshot tools put straight on the clipboard
 * as an image — this pulls that image out of a paste event, or null if
 * the clipboard held plain text/something else. */
export function extractPastedImage(e: ClipboardEvent<HTMLElement>): File | null {
  const items = e.clipboardData?.items;
  if (!items) return null;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (item.type.startsWith("image/")) {
      return item.getAsFile();
    }
  }
  return null;
}
