import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "..");

describe("public demo README", () => {
  it("uses a 16:9 PNG poster linked to the public demo and keeps fallback artifacts", () => {
    const readme = readFileSync(resolve(repositoryRoot, "README.md"), "utf8");
    expect(readme).toContain(
      "[![Watch the 60-second FreshSense product demo](docs/images/workbench/freshsense-demo-thumbnail.png)](https://freshsenseai.com/demo)",
    );
    expect(readme).toContain("docs/demo/freshsense-recruiter-demo-60s.mp4");
    expect(readme).toContain("docs/demo/freshsense-recruiter-demo-60s.mp4.sha256");
    expect(readme).toContain("docs/demo/freshsense-recruiter-demo-60s.json");

    const png = readFileSync(
      resolve(repositoryRoot, "docs/images/workbench/freshsense-demo-thumbnail.png"),
    );
    expect(png.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
    const width = png.readUInt32BE(16);
    const height = png.readUInt32BE(20);
    expect(width * 9).toBe(height * 16);
    expect(width).toBeGreaterThanOrEqual(1280);
  });
});
