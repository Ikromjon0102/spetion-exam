import { useEffect, useState } from "react";
import { apiClient } from "../../api/client";

/** Renders a stored question/option image. `<img src>` can't send an
 * Authorization header, so this fetches the bytes as a blob (through the
 * same authenticated apiClient every other request uses) and points the
 * <img> at an object URL instead — see backend's get_question_image. */
export default function AuthedImage({
  src,
  alt,
  maxHeight,
}: {
  src: string;
  alt?: string;
  maxHeight?: number;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    apiClient
      .get(src, { responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        url = URL.createObjectURL(res.data);
        setObjectUrl(url);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);

  if (!objectUrl) {
    return <div className="sp-input" style={{ height: maxHeight ?? 80, opacity: 0.5 }} />;
  }
  return (
    <img
      src={objectUrl}
      alt={alt ?? ""}
      style={{ maxWidth: "100%", maxHeight, borderRadius: "var(--radius-md)", border: "1px solid var(--border)" }}
    />
  );
}
