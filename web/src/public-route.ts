export type EntryPoint = "public-demo" | "authenticated-app";

export function selectEntryPoint(pathname: string): EntryPoint {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return normalized === "/demo" ? "public-demo" : "authenticated-app";
}
