import { EditorContent, Node, mergeAttributes, useEditor } from "@tiptap/react";
import Placeholder from "@tiptap/extension-placeholder";
import StarterKit from "@tiptap/starter-kit";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import Underline from "@tiptap/extension-underline";
import { useEffect, useState } from "react";
import { useLanguage } from "../../i18n/LanguageContext";
import { fromEditorHtml, toEditorHtml, unwrapSingleParagraph } from "../../utils/richText";
import Button from "./Button";
import { loadKatex } from "./RichText";
import "./richtext.css";
import "./richtexteditor.css";

/** A formula inside a line of text. Stored as <span data-type="inline-math"
 * data-latex="..."> — the LaTeX source only, so the content stays small and
 * sanitizable; KaTeX draws it (in the editor here, and in RichText). */
const InlineMath = Node.create({
  name: "inlineMath",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      latex: {
        default: "",
        parseHTML: (el) => el.getAttribute("data-latex") ?? "",
        renderHTML: (attrs) => ({ "data-latex": attrs.latex }),
      },
    };
  },
  parseHTML() {
    return [{ tag: 'span[data-type="inline-math"]' }];
  },
  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes(HTMLAttributes, { "data-type": "inline-math" })];
  },
  addNodeView() {
    return ({ node }) => {
      const dom = document.createElement("span");
      dom.setAttribute("data-type", "inline-math");
      dom.className = "sp-math-node";
      dom.contentEditable = "false";
      const draw = (latex: string) => {
        dom.setAttribute("data-latex", latex);
        dom.textContent = latex;
        loadKatex().then((mod) => mod.default.render(latex, dom, { throwOnError: false }));
      };
      draw(node.attrs.latex);
      return {
        dom,
        update: (updated) => {
          if (updated.type.name !== "inlineMath") return false;
          draw(updated.attrs.latex);
          return true;
        },
      };
    };
  },
});

interface Props {
  /** The stored string — rich (marker-prefixed HTML) or legacy plain text. */
  value: string;
  onChange: (stored: string) => void;
  /** One line, inline formatting only (answer options). */
  compact?: boolean;
  placeholder?: string;
  /** Called instead of pasting when the clipboard holds an image. */
  onPasteImage?: (file: File) => void;
  autoFocus?: boolean;
}

export default function RichTextEditor({ value, onChange, compact, placeholder, onPasteImage, autoFocus }: Props) {
  const { t } = useLanguage();
  const [formulaOpen, setFormulaOpen] = useState(false);
  const [latex, setLatex] = useState("");
  const [preview, setPreview] = useState<HTMLSpanElement | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        blockquote: false,
        codeBlock: false,
        horizontalRule: false,
        code: false,
        ...(compact ? { bulletList: false, orderedList: false, listItem: false } : {}),
      }),
      Underline,
      Subscript,
      Superscript,
      InlineMath,
      Placeholder.configure({ placeholder: placeholder ?? "" }),
    ],
    content: toEditorHtml(value),
    autofocus: autoFocus ? "end" : false,
    editorProps: {
      attributes: { class: "sp-editor__prose" },
      handleKeyDown: (_view, event) => compact === true && event.key === "Enter",
      handlePaste: (_view, event) => {
        const items = event.clipboardData?.items;
        if (!items || !onPasteImage) return false;
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.startsWith("image/")) {
            const file = items[i].getAsFile();
            if (file) {
              event.preventDefault();
              onPasteImage(file);
              return true;
            }
          }
        }
        return false;
      },
    },
    onUpdate: ({ editor: ed }) => {
      const html = compact ? unwrapSingleParagraph(ed.getHTML()) : ed.getHTML();
      onChange(fromEditorHtml(html, ed.isEmpty));
    },
  });

  // Live KaTeX preview inside the formula panel.
  useEffect(() => {
    if (!preview) return;
    preview.textContent = "";
    if (latex.trim()) {
      loadKatex().then((mod) => mod.default.render(latex, preview, { throwOnError: false }));
    }
  }, [latex, preview]);

  if (!editor) return null;

  const editingFormula = editor.isActive("inlineMath");

  function openFormula() {
    setLatex(editingFormula ? String(editor!.getAttributes("inlineMath").latex ?? "") : "");
    setFormulaOpen(true);
  }

  function applyFormula() {
    const source = latex.trim();
    if (!source) return;
    if (editingFormula) {
      editor!.chain().focus().updateAttributes("inlineMath", { latex: source }).run();
    } else {
      editor!.chain().focus().insertContent({ type: "inlineMath", attrs: { latex: source } }).run();
    }
    setFormulaOpen(false);
    setLatex("");
  }

  // onMouseDown + preventDefault keeps the text selection while a toolbar
  // button is pressed; a plain onClick would blur the editor first.
  const tool = (label: string, title: string, active: boolean, run: () => void) => (
    <button
      type="button"
      key={title}
      className={`sp-editor__tool${active ? " sp-editor__tool--active" : ""}`}
      title={title}
      aria-label={title}
      aria-pressed={active}
      onMouseDown={(e) => {
        e.preventDefault();
        run();
      }}
    >
      {label}
    </button>
  );

  return (
    <div className={`sp-editor${compact ? " sp-editor--compact" : ""}`}>
      <div className="sp-editor__toolbar" role="toolbar">
        {tool("B", t("richEditor.bold"), editor.isActive("bold"), () => editor.chain().focus().toggleBold().run())}
        {tool("I", t("richEditor.italic"), editor.isActive("italic"), () => editor.chain().focus().toggleItalic().run())}
        {tool("U", t("richEditor.underline"), editor.isActive("underline"), () =>
          editor.chain().focus().toggleUnderline().run()
        )}
        {tool("x₂", t("richEditor.subscript"), editor.isActive("subscript"), () =>
          editor.chain().focus().toggleSubscript().run()
        )}
        {tool("x²", t("richEditor.superscript"), editor.isActive("superscript"), () =>
          editor.chain().focus().toggleSuperscript().run()
        )}
        {!compact &&
          tool("•", t("richEditor.bulletList"), editor.isActive("bulletList"), () =>
            editor.chain().focus().toggleBulletList().run()
          )}
        {!compact &&
          tool("1.", t("richEditor.orderedList"), editor.isActive("orderedList"), () =>
            editor.chain().focus().toggleOrderedList().run()
          )}
        {tool("ƒx", t("richEditor.formula"), editingFormula, openFormula)}
      </div>

      {formulaOpen && (
        <div className="sp-editor__formula">
          <input
            className="sp-input"
            autoFocus
            value={latex}
            onChange={(e) => setLatex(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                applyFormula();
              }
              if (e.key === "Escape") setFormulaOpen(false);
            }}
            placeholder={t("richEditor.formulaPlaceholder")}
          />
          <span className="sp-editor__formula-preview" ref={setPreview} />
          <Button type="button" size="sm" onClick={applyFormula} disabled={!latex.trim()}>
            {editingFormula ? t("richEditor.formulaUpdate") : t("richEditor.formulaInsert")}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setFormulaOpen(false)}>
            {t("richEditor.cancel")}
          </Button>
          <p className="body-sm ink-muted sp-editor__formula-hint">{t("richEditor.formulaHint")}</p>
        </div>
      )}

      <EditorContent editor={editor} />
    </div>
  );
}
