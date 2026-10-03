// A4 at 96dpi (CSS px) x2, matching the html2canvas scale below — every
// exported image (daily results, class credential sheets) is always
// exactly this size regardless of how much content it holds: a short
// list gets letterboxed white space, a long one is scaled down to fit,
// since a shareable/printable document should be one consistent page.
export const A4_WIDTH_PX = 1587;
export const A4_HEIGHT_PX = 2245;

/** Captures `el` via html2canvas and composes the result onto a fixed A4
 * canvas — scaled to fit and centered, never cropped — then triggers a
 * PNG download as `filename`. */
export async function exportA4Image(el: HTMLElement, filename: string): Promise<void> {
  // Imported on demand: html2canvas is ~200 kB and only needed at the moment
  // someone presses a download button.
  const { default: html2canvas } = await import("html2canvas");
  const canvas = await html2canvas(el, { backgroundColor: "#ffffff", scale: 2, useCORS: true });

  const a4Canvas = document.createElement("canvas");
  a4Canvas.width = A4_WIDTH_PX;
  a4Canvas.height = A4_HEIGHT_PX;
  const ctx = a4Canvas.getContext("2d");
  if (!ctx) throw new Error("no 2d context");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, A4_WIDTH_PX, A4_HEIGHT_PX);
  const fitScale = Math.min(A4_WIDTH_PX / canvas.width, A4_HEIGHT_PX / canvas.height);
  const drawWidth = canvas.width * fitScale;
  const drawHeight = canvas.height * fitScale;
  ctx.drawImage(canvas, (A4_WIDTH_PX - drawWidth) / 2, (A4_HEIGHT_PX - drawHeight) / 2, drawWidth, drawHeight);

  // toBlob + an object URL, not toDataURL — a raw base64 data: URI on the
  // download attribute is unreliable in some browsers (notably Safari,
  // which has historically opened it in a new tab instead of downloading)
  // and is needlessly large in memory for an image this size. The link is
  // briefly appended to the DOM, since some browsers only honor a
  // synthetic click on an anchor that's actually in the document.
  const blob = await new Promise<Blob | null>((resolve) => a4Canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("canvas.toBlob returned null");
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.download = filename;
  link.href = url;
  document.body.appendChild(link);
  link.click();
  // Removing the anchor (and later revoking the URL) happens on a delay,
  // not right after click() — some browsers process a triggered download
  // asynchronously, and yanking the anchor out of the DOM immediately can
  // race that and silently drop the download.
  setTimeout(() => link.remove(), 1000);
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
