import { useLanguage } from "../../i18n/LanguageContext";

interface Props {
  /** Single small round toggle (cycles uz/ru) instead of the UZ|RU pill —
   * for tight spaces like the collapsed sidebar where the pill wraps
   * awkwardly. */
  compact?: boolean;
}

export default function LanguageSwitcher({ compact = false }: Props) {
  const { lang, setLang } = useLanguage();

  if (compact) {
    const next = lang === "uz" ? "ru" : "uz";
    return (
      <button
        type="button"
        onClick={() => setLang(next)}
        title={lang.toUpperCase()}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 32,
          height: 32,
          border: "1.5px solid var(--border)",
          borderRadius: "var(--radius-full)",
          background: "var(--surface-raised)",
          color: "var(--ink)",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          fontWeight: 700,
          cursor: "pointer",
          flexShrink: 0,
        }}
      >
        {lang.toUpperCase()}
      </button>
    );
  }

  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: "4px 8px",
    fontFamily: "var(--font-mono)",
    fontSize: 12,
    fontWeight: 700,
    border: "none",
    background: active ? "var(--brand-600)" : "transparent",
    color: active ? "var(--on-brand)" : "var(--ink-muted)",
    borderRadius: "var(--radius-sm)",
    cursor: "pointer",
  });

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 2,
        padding: 2,
        border: "1.5px solid var(--border)",
        borderRadius: "var(--radius-md)",
        background: "var(--surface-raised)",
        flexShrink: 0,
      }}
    >
      <button type="button" style={btnStyle(lang === "uz")} onClick={() => setLang("uz")}>
        UZ
      </button>
      <button type="button" style={btnStyle(lang === "ru")} onClick={() => setLang("ru")}>
        RU
      </button>
    </div>
  );
}
