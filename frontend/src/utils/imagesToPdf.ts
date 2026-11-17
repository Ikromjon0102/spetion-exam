/** A PDF made of full-page images, with no library: each A4 page is one JPEG
 * stretched over the page. The report is rendered as HTML (so it matches the
 * app's look and fonts exactly), captured page by page, and wrapped here. */

export interface PdfPageImage {
  jpeg: Uint8Array;
  width: number; // pixels
  height: number;
}

// A4 in PDF points (1/72 inch)
const A4_W = 595.28;
const A4_H = 841.89;

export function imagesToPdf(pages: PdfPageImage[]): Blob {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const offsets: number[] = [];
  let length = 0;
  const push = (data: string | Uint8Array) => {
    const bytes = typeof data === "string" ? encoder.encode(data) : data;
    chunks.push(bytes);
    length += bytes.length;
  };
  const object = (n: number, body: string | Uint8Array[]) => {
    offsets[n] = length;
    push(`${n} 0 obj\n`);
    if (typeof body === "string") push(body);
    else body.forEach(push);
    push("\nendobj\n");
  };

  // header + the conventional "binary file" comment line
  push(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a]));

  // objects: 1 catalog, 2 page tree, then (page, contents, image) per page
  object(1, "<< /Type /Catalog /Pages 2 0 R >>");
  const pageObj = (i: number) => 3 + i * 3;
  object(2, `<< /Type /Pages /Kids [${pages.map((_, i) => `${pageObj(i)} 0 R`).join(" ")}] /Count ${pages.length} >>`);
  pages.forEach((page, i) => {
    const contents = `q ${A4_W} 0 0 ${A4_H} 0 0 cm /Im0 Do Q`;
    object(
      pageObj(i),
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${A4_W} ${A4_H}] /Resources << /XObject << /Im0 ${pageObj(i) + 2} 0 R >> >> /Contents ${pageObj(i) + 1} 0 R >>`
    );
    object(pageObj(i) + 1, `<< /Length ${contents.length} >>\nstream\n${contents}\nendstream`);
    object(pageObj(i) + 2, [
      encoder.encode(
        `<< /Type /XObject /Subtype /Image /Width ${page.width} /Height ${page.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${page.jpeg.length} >>\nstream\n`
      ),
      page.jpeg,
      encoder.encode("\nendstream"),
    ]);
  });

  const count = 3 + pages.length * 3;
  const xref = length;
  push(`xref\n0 ${count}\n0000000000 65535 f \n`);
  for (let n = 1; n < count; n++) push(`${String(offsets[n]).padStart(10, "0")} 00000 n \n`);
  push(`trailer\n<< /Size ${count} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);

  return new Blob(chunks as BlobPart[], { type: "application/pdf" });
}
