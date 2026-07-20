export type RuntimeConfig = {
  apiBaseUrl: string;
  clientId: string;
  tenantId: string;
  tenantSubdomain: string;
  apiScope: string;
  authority: string;
};

const requiredKeys = [
  "VITE_API_BASE_URL",
  "VITE_ENTRA_CLIENT_ID",
  "VITE_ENTRA_TENANT_ID",
  "VITE_ENTRA_TENANT_SUBDOMAIN",
  "VITE_ENTRA_API_SCOPE",
] as const;

export function readRuntimeConfig(
  values: Record<string, string | undefined> = import.meta.env,
  pageUrl: string | undefined =
    typeof window === "undefined" ? undefined : window.location.href,
): { config: RuntimeConfig | null; missing: string[] } {
  const missing = requiredKeys.filter((key) => !values[key]?.trim());
  if (missing.length > 0) {
    return { config: null, missing: [...missing] };
  }

  const tenantSubdomain = values.VITE_ENTRA_TENANT_SUBDOMAIN!.trim();
  const tenantId = values.VITE_ENTRA_TENANT_ID!.trim();
  const apiBaseUrl = values.VITE_API_BASE_URL!.trim().replace(/\/$/, "");

  if (pageUrl) {
    try {
      const page = new URL(pageUrl);
      const api = new URL(apiBaseUrl);
      const loopbackHosts = new Set(["localhost", "127.0.0.1", "::1"]);
      const publicPage = !loopbackHosts.has(page.hostname);
      const unsafePublicApi =
        loopbackHosts.has(api.hostname) || api.protocol !== "https:";
      if (publicPage && unsafePublicApi) {
        return {
          config: null,
          missing: ["VITE_API_BASE_URL (public deployments require HTTPS)"],
        };
      }
    } catch {
      return {
        config: null,
        missing: ["VITE_API_BASE_URL (must be a valid URL)"],
      };
    }
  }

  return {
    config: {
      apiBaseUrl,
      clientId: values.VITE_ENTRA_CLIENT_ID!.trim(),
      tenantId,
      tenantSubdomain,
      apiScope: values.VITE_ENTRA_API_SCOPE!.trim(),
      authority: `https://${tenantSubdomain}.ciamlogin.com/${tenantId}`,
    },
    missing: [],
  };
}
