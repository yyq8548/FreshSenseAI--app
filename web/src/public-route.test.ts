import { describe, expect, it } from "vitest";

import mainSource from "./main.tsx?raw";
import { selectEntryPoint } from "./public-route";

describe("selectEntryPoint", () => {
  it.each(["/demo", "/demo/"])("selects the public demo for %s", (pathname) => {
    expect(selectEntryPoint(pathname)).toBe("public-demo");
  });

  it.each(["/", "/demo-more", "/workspace", "/DEMO"])(
    "keeps %s on the authenticated entrypoint",
    (pathname) => {
      expect(selectEntryPoint(pathname)).toBe("authenticated-app");
    },
  );

  it("keeps authentication imports out of the public entry module", () => {
    expect(mainSource).not.toContain('from "./auth"');
    expect(mainSource).not.toContain('from "./config"');
    expect(mainSource).toContain('import("./AuthenticatedRoot")');
  });
});
