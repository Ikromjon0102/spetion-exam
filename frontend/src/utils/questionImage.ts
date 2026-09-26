/** Path (not a full authenticated fetch) to a stored question/option
 * image — see AuthedImage.tsx, which is what actually loads it (an <img>
 * tag can't send the Authorization header this route requires). Shared
 * between adminApi.ts (authoring) and studentApi.ts (taking/reviewing an
 * exam) since both need to build the same URL. */
export function questionImageUrl(key: string): string {
  return `/admin/exams/uploads/image/${key}`;
}
