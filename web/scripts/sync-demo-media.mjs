import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));

function hashFile(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function requireNonEmpty(path) {
  if (statSync(path).size <= 0) throw new Error(`Demo asset is empty: ${path}`);
}

export function syncDemoMedia({
  repositoryRoot = resolve(scriptDirectory, "..", ".."),
  publicRoot = resolve(scriptDirectory, "..", "public"),
} = {}) {
  const demoRoot = join(repositoryRoot, "docs", "demo");
  const imageRoot = join(repositoryRoot, "docs", "images", "workbench");
  const videoName = "freshsense-recruiter-demo-60s.mp4";
  const checksumName = `${videoName}.sha256`;
  const manifestName = "freshsense-recruiter-demo-60s.json";
  const posterName = "freshsense-demo-thumbnail.png";
  const videoPath = join(demoRoot, videoName);
  const checksumPath = join(demoRoot, checksumName);
  const manifestPath = join(demoRoot, manifestName);
  const posterPath = join(imageRoot, posterName);

  [videoPath, checksumPath, manifestPath, posterPath].forEach(requireNonEmpty);
  const expected = readFileSync(checksumPath, "utf8").trim().split(/\s+/)[0].toLowerCase();
  const actual = hashFile(videoPath);
  if (!/^[a-f0-9]{64}$/.test(expected) || actual !== expected) {
    throw new Error("Demo video checksum mismatch");
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (String(manifest.sha256).toLowerCase() !== expected) {
    throw new Error("Demo manifest checksum mismatch");
  }

  const targetDirectory = join(publicRoot, "demo");
  mkdirSync(targetDirectory, { recursive: true });
  for (const [source, name] of [
    [videoPath, videoName],
    [checksumPath, checksumName],
    [manifestPath, manifestName],
    [posterPath, posterName],
  ]) {
    copyFileSync(source, join(targetDirectory, name));
  }

  return { sha256: expected, targetDirectory };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = syncDemoMedia();
  console.log(`Synchronized FreshSense demo ${result.sha256} to ${result.targetDirectory}`);
}
