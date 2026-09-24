/** Extracts a human-readable message from an axios error against this
 * backend. FastAPI's `detail` is usually a string, but for a 422 request-
 * validation failure it's an array of Pydantic error objects — rendering
 * that array directly as JSX crashes the page ("Objects are not valid as
 * a React child"), so always go through this instead of reading
 * `response.data.detail` directly. */
export function errorDetail(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : null))
      .filter((msg): msg is string => msg !== null);
    if (messages.length > 0) return messages.join("; ");
  }
  return fallback;
}
