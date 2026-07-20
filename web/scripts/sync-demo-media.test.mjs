import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { syncDemoMedia } from "./sync-demo-media.mjs";

function fixture() {
  const root = mkdtempSync(join(tmpdir(), "freshsense-demo-"));
  const demo = join(root, "docs", "demo");
  const images = join(root, "docs", "images", "workbench");
  const publicRoot = join(root, "web", "public");
  mkdirSync(demo, { recursive: true });
  mkdirSync(images, { recursive: true });
  const video = Buffer.from("accepted-freshsense-video");
  const sha256 = createHash("sha256").update(video).digest("hex");
  writeFileSync(join(demo, "freshsense-recruiter-demo-60s.mp4"), video);
  writeFileSync(
    join(demo, "freshsense-recruiter-demo-60s.mp4.sha256"),
    `${sha256} *freshsense-recruiter-demo-60s.mp4\n`,
  );
  writeFileSync(
    join(demo, "freshsense-recruiter-demo-60s.json"),
    JSON.stringify({ sha256 }),
  );
  writeFileSync(join(images, "freshsense-demo-thumbnail.png"), Buffer.from("png-poster"));
  return { root, publicRoot, sha256, demo };
}

describe("syncDemoMedia", () => {
  it("verifies and copies the complete public demo package", () => {
    const item = fixture();
    const result = syncDemoMedia({
      repositoryRoot: item.root,
      publicRoot: item.publicRoot,
    });
    expect(result.sha256).toBe(item.sha256);
    expect(
      readFileSync(
        join(result.targetDirectory, "freshsense-recruiter-demo-60s.mp4"),
        "utf8",
      ),
    ).toBe("accepted-freshsense-video");
    expect(
      readFileSync(join(result.targetDirectory, "freshsense-demo-thumbnail.png"), "utf8"),
    ).toBe("png-poster");
  });

  it("fails closed when the video checksum changes", () => {
    const item = fixture();
    writeFileSync(join(item.demo, "freshsense-recruiter-demo-60s.mp4"), "tampered");
    expect(() =>
      syncDemoMedia({ repositoryRoot: item.root, publicRoot: item.publicRoot }),
    ).toThrow("Demo video checksum mismatch");
  });
});
