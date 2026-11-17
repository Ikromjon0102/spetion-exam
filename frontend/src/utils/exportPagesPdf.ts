import { imagesToPdf, type PdfPageImage } from "./imagesToPdf";

/** Captures each page element (already laid out at A4 proportions) and
 * downloads them as one PDF. */
export async function exportPagesPdf(pages: HTMLElement[], filename: string): Promise<void> {
  // on demand: html2canvas is ~200 kB and only needed when this button is pressed
  const { default: html2canvas } = await import("html2canvas");
  if (document.fonts) await document.fonts.ready;
  await Promise.all(
    pages.flatMap((page) => Array.from(page.querySelectorAll("img")).map((img) => img.decode().catch(() => undefined)))
  );

  const images: PdfPageImage[] = [];
  for (const page of pages) {
    const canvas = await html2canvas(page, { backgroundColor: "#ffffff", scale: 2, useCORS: true });
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) throw new Error("canvas.toBlob returned null");
    images.push({ jpeg: new Uint8Array(await blob.arrayBuffer()), width: canvas.width, height: canvas.height });
  }

  const url = URL.createObjectURL(imagesToPdf(images));
  const link = document.createElement("a");
  link.download = filename;
  link.href = url;
  document.body.appendChild(link);
  link.click();
  setTimeout(() => link.remove(), 1000);
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

/** "Aliyev Vali" -> "aliyev-vali": a download name every file system accepts. */
export function fileSlug(text: string): string {
  return (
    text
      .normalize("NFKD")
      .replace(/[̀-ͯ'’`]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "oquvchi"
  );
}
