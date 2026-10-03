// Question and option text is either plain text or sanitized rich HTML. Rich
// content carries this marker as its first characters — the same marker the
// backend (app/core/rich_text.py) uses and enforces. Anything without it is
// plain text and is never interpreted as HTML.
export const RICH_PREFIX = "<!--sp-rich-->";

export function isRich(text: string | null | undefined): boolean {
  return !!text && text.startsWith(RICH_PREFIX);
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Editor input: rich content as bare HTML, plain text converted to
 * paragraphs (blank-line separated blocks, single newlines kept as <br>). */
export function toEditorHtml(text: string): string {
  if (isRich(text)) return text.slice(RICH_PREFIX.length);
  if (!text.trim()) return "";
  return text
    .split(/\n{2,}/)
    .map((block) => `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

/** Editor output -> stored string. Empty editors store "" so the existing
 * "needs text or an image" validation keeps working. */
export function fromEditorHtml(html: string, isEmpty: boolean): string {
  return isEmpty ? "" : RICH_PREFIX + html;
}

/** Option text is shown inline inside a button/label, so the editor's single
 * wrapping <p> is dropped — block elements don't belong there. */
export function unwrapSingleParagraph(html: string): string {
  const match = html.match(/^<p>([\s\S]*)<\/p>$/);
  return match && !match[1].includes("<p>") ? match[1] : html;
}
