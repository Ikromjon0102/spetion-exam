import qrcode from "qrcode-generator";

/** A QR code for `text` as a data: URL. Synchronous on purpose — the
 * credentials sheet is rendered off-screen and captured the instant it
 * mounts (auto-download after a password reset), so an async generator would
 * leave the QR missing from the first export. */
export function qrDataUrl(text: string, cellSize = 6): string {
  const qr = qrcode(0, "M");
  qr.addData(text);
  qr.make();
  return qr.createDataURL(cellSize, 2);
}
