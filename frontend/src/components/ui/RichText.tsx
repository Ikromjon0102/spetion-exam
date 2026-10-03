import DOMPurify from "dompurify";
import { useEffect, useMemo, useRef } from "react";
import { RICH_PREFIX, isRich } from "../../utils/richText";
import "./richtext.css";

// Keep in step with ALLOWED_TAGS / ALLOWED_ATTRIBUTES in
// backend/app/core/rich_text.py. The server already sanitizes on the way in;
// this is the second layer, applied again just before anything touches the DOM.
const PURIFY_CONFIG = {
  ALLOWED_TAGS: ["p", "br", "strong", "em", "u", "s", "sub", "sup", "ul", "ol", "li", "span", "code"],
  ALLOWED_ATTR: ["data-type", "data-latex"],
};

let katexPromise: Promise<typeof import("katex")> | null = null;

/** KaTeX (and its stylesheet + fonts) is only fetched the first time a
 * formula actually has to be drawn. */
export function loadKatex() {
  katexPromise ??= Promise.all([import("katex"), import("katex/dist/katex.min.css")]).then(([mod]) => mod);
  return katexPromise;
}

export function renderFormulas(root: HTMLElement) {
  const nodes = root.querySelectorAll<HTMLElement>('span[data-type="inline-math"]');
  if (nodes.length === 0) return;
  loadKatex().then((mod) => {
    const katex = mod.default;
    nodes.forEach((node) => {
      katex.render(node.getAttribute("data-latex") ?? "", node, { throwOnError: false, output: "htmlAndMathml" });
    });
  });
}

interface Props {
  text: string;
  className?: string;
  /** Render as a block (question prompts, which may hold several paragraphs
   * and lists); the default is inline, for option text inside buttons. */
  block?: boolean;
}

/** Shows question/option text: sanitized HTML (with formulas drawn by KaTeX)
 * when it is rich, otherwise the plain text exactly as before. */
export default function RichText({ text, className, block }: Props) {
  const ref = useRef<HTMLElement>(null);
  const rich = isRich(text);
  const html = useMemo(
    () => (rich ? String(DOMPurify.sanitize(text.slice(RICH_PREFIX.length), PURIFY_CONFIG)) : ""),
    [rich, text]
  );

  useEffect(() => {
    if (rich && ref.current) renderFormulas(ref.current);
  }, [rich, html]);

  const Tag = block ? "div" : "span";
  if (!rich) {
    return (
      <Tag className={className} style={{ whiteSpace: "pre-wrap" }}>
        {text}
      </Tag>
    );
  }
  return (
    <Tag
      ref={ref as React.RefObject<never>}
      className={`sp-rich ${className ?? ""}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
