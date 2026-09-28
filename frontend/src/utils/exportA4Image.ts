import html2canvas from "html2canvas";

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

  const link = document.createElement("a");
  link.download = filename;
  link.href = a4Canvas.toDataURL("image/png");
  link.click();
}
