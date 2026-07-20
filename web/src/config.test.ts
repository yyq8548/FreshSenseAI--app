import { describe, expect, it } from "vitest";

import { readRuntimeConfig } from "./config";

describe("readRuntimeConfig", () => {
  it("reports every missing public setting without inventing defaults", () => {
    const result = readRuntimeConfig({});
    expect(result.config).toBeNull();
    expect(result.missing).toContain("VITE_ENTRA_CLIENT_ID");
    expect(result.missing).toContain("VITE_ENTRA_API_SCOPE");
  });

  it("builds an External ID authority and normalizes the API URL", () => {
    const result = readRuntimeConfig({
      VITE_API_BASE_URL: "https://api.freshsense.example/",
      VITE_ENTRA_CLIENT_ID: "spa-client",
      VITE_ENTRA_TENANT_ID: "tenant-id",
      VITE_ENTRA_TENANT_SUBDOMAIN: "freshsense",
      VITE_ENTRA_API_SCOPE: "api://api-client/access_as_user",
    }, "https://freshsenseai.com/");
    expect(result.config?.authority).toBe(
      "https://freshsense.ciamlogin.com/tenant-id",
    );
    expect(result.config?.apiBaseUrl).toBe("https://api.freshsense.example");
  });

  it("rejects a loopback API URL on a public deployment", () => {
    const result = readRuntimeConfig(
      {
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
        VITE_ENTRA_CLIENT_ID: "spa-client",
        VITE_ENTRA_TENANT_ID: "tenant-id",
        VITE_ENTRA_TENANT_SUBDOMAIN: "freshsense",
        VITE_ENTRA_API_SCOPE: "api://api-client/access_as_user",
      },
      "https://freshsenseai.com/",
    );

    expect(result.config).toBeNull();
    expect(result.missing).toContain(
      "VITE_API_BASE_URL (public deployments require HTTPS)",
    );
  });

  it("allows a loopback API URL during local development", () => {
    const result = readRuntimeConfig(
      {
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
        VITE_ENTRA_CLIENT_ID: "spa-client",
        VITE_ENTRA_TENANT_ID: "tenant-id",
        VITE_ENTRA_TENANT_SUBDOMAIN: "freshsense",
        VITE_ENTRA_API_SCOPE: "api://api-client/access_as_user",
      },
      "http://localhost:5173/",
    );

    expect(result.config?.apiBaseUrl).toBe("http://127.0.0.1:8000");
  });
});
