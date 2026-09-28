import { forwardRef } from "react";
import Logo from "./Logo";
import sparkMarkRed from "../../assets/logos/spetion-mark-red.png";

// Same hardcoded-color approach as DailyResultsPage.tsx's captured card —
// this image leaves the app (printed/shared by the homeroom teacher), so
// it must look the same regardless of the viewer's theme and must not
// depend on html2canvas resolving var(--...) correctly.
const CARD_INK = "#1a1a1a";
const CARD_MUTED = "#6b6b6b";
const CARD_BRAND = "#dd1808";
const CARD_BORDER = "#ececec";
const CARD_ZEBRA = "#fdf5f4";

export interface CredentialRow {
  full_name: string;
  username: string;
  password: string;
}

interface Props {
  classTitle: string;
  subtitle: string;
  rows: CredentialRow[];
  studentColumnLabel: string;
  usernameColumnLabel: string;
  passwordColumnLabel: string;
  footerLabel: string;
}

/** A printable A4 roster of login credentials — handed to a homeroom
 * teacher right after bulk-importing a class or resetting its shared
 * password, since the plaintext password is only ever available in the
 * browser at that exact moment (passwords are hashed at rest, never
 * recoverable later). Same visual language as DailyResultsPage.tsx's
 * card (red banner, tiled brand mark, zebra rows) for a consistent
 * "this came from Spetion" look across every exported document. */
const CredentialsSheetCard = forwardRef<HTMLDivElement, Props>(function CredentialsSheetCard(
  { classTitle, subtitle, rows, studentColumnLabel, usernameColumnLabel, passwordColumnLabel, footerLabel },
  ref
) {
  return (
    <div
      ref={ref}
      style={{
        position: "relative",
        backgroundColor: "#ffffff",
        color: CARD_INK,
        borderRadius: 12,
        width: "fit-content",
        minWidth: 480,
        border: `1px solid ${CARD_BORDER}`,
        fontFamily: "Inter, system-ui, sans-serif",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `url(${sparkMarkRed})`,
          backgroundRepeat: "repeat",
          backgroundSize: "70px 70px",
          opacity: 0.06,
        }}
      />
      <div style={{ position: "relative" }}>
        <div style={{ height: 8, background: CARD_BRAND }} />

        <div style={{ padding: "28px 32px 16px", textAlign: "center" }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
            <Logo tone="red" height={30} />
          </div>
          <h2 style={{ fontSize: 24, letterSpacing: 1, margin: 0, marginBottom: 4 }}>{classTitle}</h2>
          <p style={{ fontSize: 14, color: CARD_MUTED, margin: 0 }}>{subtitle}</p>
        </div>

        <div style={{ padding: "0 32px 20px" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%", background: "#ffffff" }}>
            <thead>
              <tr style={{ background: CARD_BRAND, color: "#ffffff" }}>
                <th style={{ padding: "8px 10px", fontSize: 12 }}>#</th>
                <th style={{ textAlign: "left", padding: "8px 10px", fontSize: 12 }}>{studentColumnLabel}</th>
                <th style={{ textAlign: "left", padding: "8px 10px", fontSize: 12 }}>{usernameColumnLabel}</th>
                <th style={{ textAlign: "left", padding: "8px 10px", fontSize: 12 }}>{passwordColumnLabel}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.username} style={{ background: i % 2 === 1 ? CARD_ZEBRA : "#ffffff" }}>
                  <td style={{ padding: "8px 10px", color: CARD_MUTED }}>{i + 1}</td>
                  <td style={{ padding: "8px 10px", whiteSpace: "nowrap", fontWeight: 600 }}>{row.full_name}</td>
                  <td style={{ padding: "8px 10px", whiteSpace: "nowrap", fontFamily: "'Space Mono', monospace" }}>
                    {row.username}
                  </td>
                  <td style={{ padding: "8px 10px", whiteSpace: "nowrap", fontFamily: "'Space Mono', monospace" }}>
                    {row.password}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div
          style={{
            padding: "12px 32px",
            borderTop: `1px solid ${CARD_BORDER}`,
            textAlign: "center",
            fontSize: 12,
            color: CARD_MUTED,
          }}
        >
          {footerLabel}
        </div>
      </div>
    </div>
  );
});

export default CredentialsSheetCard;
