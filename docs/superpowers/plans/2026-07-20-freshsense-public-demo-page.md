# FreshSense Public Demo Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a no-login player at `https://freshsenseai.com/demo` and replace the README text link with a real 16:9 video thumbnail that opens that page.

**Architecture:** The SPA bootstrap selects `/demo` before importing runtime configuration or Microsoft authentication. A public React page plays a build-copied version of the canonical recruiter MP4, while a deterministic prebuild script verifies and copies the canonical video package into Vite's public output. The README uses a real video-frame poster linked to the public route and keeps direct GitHub artifact links.

**Tech Stack:** React 19.2.7, TypeScript 7.0.2, Vite 8.1.5, Vitest 4.1.10, Azure Static Web Apps, Node.js 24, Microsoft Edge/Chromium, GitHub Markdown.

## Global Constraints

- `/demo` and `/demo/` must be public and must not initialize Microsoft Entra authentication.
- Playback starts with `autoPlay`, `muted`, `playsInline`, visible native controls, and `preload="metadata"`.
- Enabling sound requires a user action through a clearly labelled button or native control.
- The canonical MP4 remains `docs/demo/freshsense-recruiter-demo-60s.mp4`; do not commit a second video copy.
- The build must fail if the MP4 checksum, manifest, poster, or source files are missing or inconsistent.
- The README thumbnail must be a real 16:9 frame with a centered play symbol and must link to `https://freshsenseai.com/demo`.
- Keep the direct MP4, SHA-256, and manifest links in the README.
- Do not add analytics, third-party video embeds, API calls, or changes to the authenticated workbench.
- Do not claim food-safety certification; repeat the visual-decision-support limitation on the public page.

---

## File map

| File | Responsibility |
| --- | --- |
| `web/src/public-route.ts` | Pure pathname normalization and public/authenticated entry selection |
| `web/src/public-route.test.ts` | Public path and bootstrap-source regression tests |
| `web/src/AuthenticatedRoot.tsx` | Existing themed configuration/MSAL bootstrap moved out of the public entry bundle |
| `web/src/PublicDemoPage.tsx` | Public video player, sound action, navigation, and safety copy |
| `web/src/public-demo.test.tsx` | Static markup and sound-helper behavior tests |
| `web/src/main.tsx` | Minimal entrypoint that renders public demo or dynamically imports authenticated root |
| `web/src/styles.css` | Responsive public-demo presentation and focus/reduced-motion styles |
| `web/scripts/sync-demo-media.mjs` | Checksum-validates and copies canonical demo assets into generated `web/public/demo/` |
| `web/scripts/sync-demo-media.test.mjs` | Success and failure tests for build-time asset synchronization |
| `web/scripts/readme-demo.test.mjs` | README link, poster, and poster-dimension contract |
| `web/package.json` | Runs media synchronization before the Vite build |
| `.gitignore` | Ignores generated `web/public/demo/` files |
| `docs/images/workbench/freshsense-demo-thumbnail.png` | Canonical README/player poster derived from the accepted video |
| `README.md` | Clickable poster and fallback artifact links |

---

### Task 1: Split the public route from authenticated bootstrap

**Files:**
- Create: `web/src/public-route.ts`
- Create: `web/src/public-route.test.ts`
- Create: `web/src/AuthenticatedRoot.tsx`
- Modify: `web/src/main.tsx`

**Interfaces:**
- Produces: `selectEntryPoint(pathname: string): "public-demo" | "authenticated-app"`
- Produces: `AuthenticatedRoot: React.FC`
- Consumes: existing `App`, `ConfigurationRequired`, `createMsalClient`, and `readRuntimeConfig`

- [ ] **Step 1: Write the failing route and bootstrap-shape tests**

Create `web/src/public-route.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

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
    const source = readFileSync(resolve(process.cwd(), "src/main.tsx"), "utf8");
    expect(source).not.toContain('from "./auth"');
    expect(source).not.toContain('from "./config"');
    expect(source).toContain('import("./AuthenticatedRoot")');
  });
});
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
cd web
npm.cmd test -- src/public-route.test.ts
```

Expected: FAIL because `./public-route` and `AuthenticatedRoot` do not exist and `main.tsx` still statically imports authentication.

- [ ] **Step 3: Implement the path selector**

Create `web/src/public-route.ts`:

```ts
export type EntryPoint = "public-demo" | "authenticated-app";

export function selectEntryPoint(pathname: string): EntryPoint {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return normalized === "/demo" ? "public-demo" : "authenticated-app";
}
```

- [ ] **Step 4: Move the existing authenticated root without behavior changes**

Create `web/src/AuthenticatedRoot.tsx` with the complete existing authenticated
bootstrap moved out of the public entry module:

```tsx
import { useEffect, useMemo, useState } from "react";
import { MsalProvider } from "@azure/msal-react";
import {
  createDarkTheme,
  createLightTheme,
  FluentProvider,
  type BrandVariants,
} from "@fluentui/react-components";

import { App, ConfigurationRequired } from "./App";
import { createMsalClient } from "./auth";
import { readRuntimeConfig } from "./config";

const freshSenseBrand: BrandVariants = {
  10: "#071508",
  20: "#102814",
  30: "#173A1F",
  40: "#1C4D28",
  50: "#216132",
  60: "#26753D",
  70: "#2C8948",
  80: "#359D55",
  90: "#4BAC68",
  100: "#66BA7C",
  110: "#7FC790",
  120: "#98D3A4",
  130: "#B0DFB8",
  140: "#C8EACC",
  150: "#E0F4E1",
  160: "#F1FAF1",
};

const lightTheme = createLightTheme(freshSenseBrand);
const darkTheme = createDarkTheme(freshSenseBrand);

function useDarkMode() {
  const [isDark, setIsDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setIsDark(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return isDark;
}

export function AuthenticatedRoot() {
  const isDark = useDarkMode();
  const runtime = useMemo(() => readRuntimeConfig(), []);
  const [client, setClient] = useState<ReturnType<typeof createMsalClient> | null>(null);
  const [startupError, setStartupError] = useState<string | null>(null);

  useEffect(() => {
    if (!runtime.config) return;
    const msal = createMsalClient(runtime.config);
    msal
      .initialize()
      .then(() => setClient(msal))
      .catch(() => setStartupError("Microsoft sign-in could not be initialized."));
  }, [runtime.config]);

  return (
    <FluentProvider theme={isDark ? darkTheme : lightTheme} className="provider">
      {!runtime.config ? (
        <ConfigurationRequired missing={runtime.missing} />
      ) : startupError ? (
        <ConfigurationRequired missing={[]} error={startupError} />
      ) : !client ? (
        <div className="startup-status" role="status">Preparing secure sign-in...</div>
      ) : (
        <MsalProvider instance={client}>
          <App config={runtime.config} />
        </MsalProvider>
      )}
    </FluentProvider>
  );
}
```

- [ ] **Step 5: Replace `main.tsx` with the public-first bootstrap**

Use this implementation in `web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { PublicDemoPage } from "./PublicDemoPage";
import { selectEntryPoint } from "./public-route";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);

if (selectEntryPoint(window.location.pathname) === "public-demo") {
  root.render(
    <StrictMode>
      <PublicDemoPage />
    </StrictMode>,
  );
} else {
  import("./AuthenticatedRoot")
    .then(({ AuthenticatedRoot }) => {
      root.render(
        <StrictMode>
          <AuthenticatedRoot />
        </StrictMode>,
      );
    })
    .catch(() => {
      root.render(<div className="startup-status" role="alert">FreshSense could not start.</div>);
    });
}
```

Create the minimal Task 1 shell in `web/src/PublicDemoPage.tsx` so this task
compiles before Task 2 replaces it with the complete player:

```tsx
export function PublicDemoPage() {
  return <main>FreshSense demo</main>;
}
```

- [ ] **Step 6: Run the focused and full web checks**

Run:

```powershell
cd web
npm.cmd test -- src/public-route.test.ts
npm.cmd test
npm.cmd run typecheck
Select-String -LiteralPath public\staticwebapp.config.json -Pattern '"navigationFallback"'
```

Expected: route tests PASS, all existing web tests PASS, TypeScript exits 0, and the Azure Static Web Apps configuration retains its SPA navigation fallback so `/demo` resolves through `index.html`.

- [ ] **Step 7: Commit Task 1**

```powershell
git add web/src/public-route.ts web/src/public-route.test.ts web/src/AuthenticatedRoot.tsx web/src/PublicDemoPage.tsx web/src/main.tsx
git commit -m "Add public FreshSense entry route"
```

---

### Task 2: Build the accessible public video page

**Files:**
- Modify: `web/src/PublicDemoPage.tsx`
- Create: `web/src/public-demo.test.tsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Produces: `enableVideoSound(video: Pick<HTMLVideoElement, "muted" | "play">): Promise<void>`
- Produces: `PublicDemoPage: React.FC`
- Consumes: `/demo/freshsense-recruiter-demo-60s.mp4` and `/demo/freshsense-demo-thumbnail.png`

- [ ] **Step 1: Write failing page and sound-control tests**

Create `web/src/public-demo.test.tsx`:

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { enableVideoSound, PublicDemoPage } from "./PublicDemoPage";

describe("PublicDemoPage", () => {
  it("renders the public muted-autoplay player and fallback actions", () => {
    const html = renderToStaticMarkup(<PublicDemoPage />);
    expect(html).toContain("FreshSense in 60 seconds");
    expect(html).toContain("autoplay");
    expect(html).toContain("muted");
    expect(html).toContain("playsinline");
    expect(html).toContain('preload="metadata"');
    expect(html).toContain('/demo/freshsense-recruiter-demo-60s.mp4');
    expect(html).toContain('/demo/freshsense-demo-thumbnail.png');
    expect(html).toContain("Enable sound");
    expect(html).toContain("Open FreshSense");
    expect(html).toContain("View source on GitHub");
    expect(html).toContain("Download MP4");
    expect(html).toContain("does not certify that food is safe");
  });

  it("unmutes and resumes the current video after user action", async () => {
    const play = vi.fn().mockResolvedValue(undefined);
    const video = { muted: true, play };
    await enableVideoSound(video);
    expect(video.muted).toBe(false);
    expect(play).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
cd web
npm.cmd test -- src/public-demo.test.tsx
```

Expected: FAIL because the Task 1 shell lacks the video, actions, safety copy, and sound helper.

- [ ] **Step 3: Implement the page**

Replace `web/src/PublicDemoPage.tsx` with:

```tsx
import { useRef, useState } from "react";

const githubRepository = "https://github.com/yyq8548/FreshSenseAI--app";
const githubVideo = `${githubRepository}/blob/main/docs/demo/freshsense-recruiter-demo-60s.mp4?raw=1`;

export async function enableVideoSound(
  video: Pick<HTMLVideoElement, "muted" | "play">,
): Promise<void> {
  video.muted = false;
  await video.play();
}

export function PublicDemoPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const [playbackMessage, setPlaybackMessage] = useState(
    "Muted autoplay is on. Enable sound when you are ready.",
  );

  const handleEnableSound = async () => {
    const video = videoRef.current;
    if (!video) return;
    try {
      await enableVideoSound(video);
      setMuted(false);
      setPlaybackMessage("Sound is on.");
    } catch {
      video.muted = false;
      setMuted(false);
      setPlaybackMessage("Sound is on. Use the native play control to resume.");
    }
  };

  return (
    <div className="demo-page">
      <header className="demo-header">
        <a className="demo-brand" href="/" aria-label="Open FreshSense">
          <span className="demo-brand-mark" aria-hidden="true">FS</span>
          <span><strong>FreshSense</strong><small>Public product demo</small></span>
        </a>
        <a className="demo-header-link" href={githubRepository}>GitHub repository</a>
      </header>

      <main className="demo-main">
        <p className="demo-eyebrow">FRESHSENSE · PRODUCT DOCUMENTARY</p>
        <h1>FreshSense in 60 seconds</h1>
        <p className="demo-lede">
          Follow a grocery inspection from multi-photo upload through computer
          vision, bounded Agent follow-up, human review, Manager Chat, and reporting.
        </p>

        <section className="demo-player-card" aria-label="FreshSense product video">
          <video
            ref={videoRef}
            className="demo-video"
            autoPlay
            muted={muted}
            playsInline
            controls
            preload="metadata"
            poster="/demo/freshsense-demo-thumbnail.png"
            onVolumeChange={(event) => setMuted(event.currentTarget.muted)}
          >
            <source src="/demo/freshsense-recruiter-demo-60s.mp4" type="video/mp4" />
            Your browser cannot play this video. <a href={githubVideo}>Download the MP4.</a>
          </video>
          <div className="demo-audio-row">
            <button type="button" onClick={handleEnableSound} disabled={!muted}>
              {muted ? "Enable sound" : "Sound enabled"}
            </button>
            <span role="status" aria-live="polite">{playbackMessage}</span>
          </div>
        </section>

        <nav className="demo-actions" aria-label="Demo links">
          <a className="demo-primary-action" href="/">Open FreshSense</a>
          <a href={githubRepository}>View source on GitHub</a>
          <a href={githubVideo}>Download MP4</a>
        </nav>

        <aside className="demo-safety-note">
          FreshSense evaluates visible image patterns and does not certify that food is safe.
          Store staff make the final decision after inspecting the physical fruit.
        </aside>
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Add responsive public-page styles**

Append the following focused rules to `web/src/styles.css`:

```css
.demo-page {
  min-height: 100vh;
  color: #172019;
  background: radial-gradient(circle at 80% 0%, #e8f5e9 0, transparent 34rem), #f7f9f6;
}

.demo-header {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 14px clamp(20px, 5vw, 72px);
  border-bottom: 1px solid #dce5dc;
  background: rgba(255, 255, 255, 0.9);
}

.demo-brand { display: flex; align-items: center; gap: 12px; color: inherit; text-decoration: none; }
.demo-brand span:last-child { display: grid; gap: 2px; }
.demo-brand small { color: #5e6b61; }
.demo-brand-mark {
  width: 42px; height: 42px; display: grid; place-items: center;
  border-radius: 10px; color: #fff; background: #2f9e55; font-weight: 800;
}
.demo-header-link { color: #216d3b; font-weight: 650; }
.demo-main { width: min(1120px, calc(100% - 40px)); margin: 0 auto; padding: 64px 0 80px; }
.demo-eyebrow { margin: 0 0 12px; color: #2b7a43; font-size: 13px; font-weight: 800; letter-spacing: 0.14em; }
.demo-main h1 { max-width: 820px; margin: 0; font-size: clamp(42px, 7vw, 76px); line-height: 0.98; letter-spacing: -0.045em; }
.demo-lede { max-width: 760px; margin: 24px 0 34px; color: #4d5a50; font-size: clamp(18px, 2vw, 23px); line-height: 1.55; }
.demo-player-card { overflow: hidden; border: 1px solid #cfdacf; border-radius: 20px; background: #101412; box-shadow: 0 28px 80px rgba(28, 77, 40, 0.16); }
.demo-video { width: 100%; aspect-ratio: 16 / 9; display: block; background: #0b0f0c; }
.demo-audio-row { display: flex; align-items: center; gap: 16px; padding: 14px 18px; color: #dce7de; background: #172019; }
.demo-audio-row button { min-height: 42px; padding: 0 18px; border: 0; border-radius: 999px; color: #0f2416; background: #a9e5b8; font-weight: 750; cursor: pointer; }
.demo-audio-row button:disabled { cursor: default; opacity: 0.7; }
.demo-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 14px 24px; margin: 28px 0; }
.demo-actions a { color: #216d3b; font-weight: 700; }
.demo-actions .demo-primary-action { padding: 12px 18px; border-radius: 10px; color: #fff; background: #287f46; text-decoration: none; }
.demo-safety-note { padding: 18px 20px; border-left: 4px solid #e2ac42; color: #5c4b22; background: #fff7e2; line-height: 1.5; }
.demo-page a:focus-visible, .demo-page button:focus-visible { outline: 3px solid #126fd6; outline-offset: 3px; }

@media (max-width: 640px) {
  .demo-header { align-items: flex-start; }
  .demo-header-link { display: none; }
  .demo-main { width: min(100% - 24px, 1120px); padding-top: 44px; }
  .demo-audio-row { align-items: flex-start; flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  .demo-page *, .demo-page *::before, .demo-page *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Run RED-to-GREEN verification and commit**

Run:

```powershell
cd web
npm.cmd test -- src/public-demo.test.tsx
npm.cmd test
npm.cmd run typecheck
cd ..
git add web/src/PublicDemoPage.tsx web/src/public-demo.test.tsx web/src/styles.css
git commit -m "Build public FreshSense demo player"
```

Expected: all web tests PASS and TypeScript exits 0.

---

### Task 3: Add deterministic media synchronization

**Files:**
- Create: `web/scripts/sync-demo-media.mjs`
- Create: `web/scripts/sync-demo-media.test.mjs`
- Modify: `web/package.json`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `syncDemoMedia({repositoryRoot, publicRoot}): {sha256: string; targetDirectory: string}`
- Consumes: canonical MP4, checksum, manifest, and `docs/images/workbench/freshsense-demo-thumbnail.png`

- [ ] **Step 1: Write failing synchronization tests**

Create `web/scripts/sync-demo-media.test.mjs`:

```js
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
  writeFileSync(join(demo, "freshsense-recruiter-demo-60s.mp4.sha256"), `${sha256} *freshsense-recruiter-demo-60s.mp4\n`);
  writeFileSync(join(demo, "freshsense-recruiter-demo-60s.json"), JSON.stringify({ sha256 }));
  writeFileSync(join(images, "freshsense-demo-thumbnail.png"), Buffer.from("png-poster"));
  return { root, publicRoot, sha256, demo };
}

describe("syncDemoMedia", () => {
  it("verifies and copies the complete public demo package", () => {
    const item = fixture();
    const result = syncDemoMedia({ repositoryRoot: item.root, publicRoot: item.publicRoot });
    expect(result.sha256).toBe(item.sha256);
    expect(readFileSync(join(result.targetDirectory, "freshsense-recruiter-demo-60s.mp4"), "utf8"))
      .toBe("accepted-freshsense-video");
    expect(readFileSync(join(result.targetDirectory, "freshsense-demo-thumbnail.png"), "utf8"))
      .toBe("png-poster");
  });

  it("fails closed when the video checksum changes", () => {
    const item = fixture();
    writeFileSync(join(item.demo, "freshsense-recruiter-demo-60s.mp4"), "tampered");
    expect(() => syncDemoMedia({ repositoryRoot: item.root, publicRoot: item.publicRoot }))
      .toThrow("Demo video checksum mismatch");
  });
});
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
cd web
npm.cmd test -- scripts/sync-demo-media.test.mjs
```

Expected: FAIL because `sync-demo-media.mjs` does not exist.

- [ ] **Step 3: Implement the synchronization script**

Create `web/scripts/sync-demo-media.mjs`:

```js
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
  ]) copyFileSync(source, join(targetDirectory, name));

  return { sha256: expected, targetDirectory };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = syncDemoMedia();
  console.log(`Synchronized FreshSense demo ${result.sha256} to ${result.targetDirectory}`);
}
```

- [ ] **Step 4: Wire synchronization into the build and ignore generated copies**

Add these scripts in `web/package.json`:

```json
"demo:sync": "node scripts/sync-demo-media.mjs",
"prebuild": "npm run demo:sync"
```

Append to `.gitignore`:

```text
web/public/demo/
```

- [ ] **Step 5: Run the tests and commit**

```powershell
cd web
npm.cmd test -- scripts/sync-demo-media.test.mjs
npm.cmd test
cd ..
git add .gitignore web/package.json web/scripts/sync-demo-media.mjs web/scripts/sync-demo-media.test.mjs
git commit -m "Verify public demo media at build time"
```

Expected: synchronization tests and the full web suite PASS. The production build is intentionally deferred until the poster exists in Task 4.

---

### Task 4: Create the real video poster and update the README

**Files:**
- Create: `docs/images/workbench/freshsense-demo-thumbnail.png`
- Create: `web/scripts/readme-demo.test.mjs`
- Modify: `README.md`

**Interfaces:**
- Produces: exact 16:9 PNG poster used by README and player
- Consumes: accepted recruiter MP4 and `https://freshsenseai.com/demo`

- [ ] **Step 1: Write the failing README and PNG contract test**

Create `web/scripts/readme-demo.test.mjs`:

```js
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
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
cd web
npm.cmd test -- scripts/readme-demo.test.mjs
```

Expected: FAIL because the poster does not exist and README still uses a text-only link.

- [ ] **Step 3: Extract and inspect a representative real frame**

Use the tracked Remotion FFmpeg wrapper to extract the batch-inspection scene:

```powershell
cd video
node node_modules/@remotion/cli/remotion-cli.js ffmpeg -ss 00:00:15 -i ..\docs\demo\freshsense-recruiter-demo-60s.mp4 -frames:v 1 -vf scale=1920:1080 .tmp\demo-thumbnail-source.png -y
```

Inspect `video/.tmp/demo-thumbnail-source.png` with the image viewer. Confirm it
shows the real FreshSense UI, readable product context, and no transient error.

- [ ] **Step 4: Create the poster with the built-in image generation editor**

Use the extracted frame as the only referenced image and this exact edit prompt:

```text
Use case: precise-object-edit
Asset type: GitHub README and public video-player poster
Primary request: Add a centered circular play button to this exact FreshSense video frame.
Input images: Image 1 is the accepted real FreshSense demo frame and must remain recognizable and faithful.
Composition/framing: preserve the 16:9 frame; place one medium white triangular play icon inside a translucent deep-green circle at the exact center.
Style/medium: polished product-documentary thumbnail, restrained and professional.
Constraints: preserve the real application layout, screenshots, text, colors, and proportions; change only overall contrast treatment and the centered play control; output a 16:9 PNG at least 1280 pixels wide.
Avoid: invented UI, altered labels, extra text, logos, gradients over the entire image, people, fruit photography, watermark.
```

Inspect the generated result. Reject any result that changes interface text or
geometry. Save the accepted project-bound asset exactly as:

`docs/images/workbench/freshsense-demo-thumbnail.png`

- [ ] **Step 5: Replace the README text link with the poster**

Under `## 60-second product demo`, use:

```markdown
[![Watch the 60-second FreshSense product demo](docs/images/workbench/freshsense-demo-thumbnail.png)](https://freshsenseai.com/demo)

[Open the public video page](https://freshsenseai.com/demo) |
[Download the MP4](docs/demo/freshsense-recruiter-demo-60s.mp4) |
[SHA-256 checksum](docs/demo/freshsense-recruiter-demo-60s.mp4.sha256) |
[Media manifest](docs/demo/freshsense-recruiter-demo-60s.json)
```

Keep the existing two-paragraph description below those links.

- [ ] **Step 6: Run poster, README, media-sync, and build verification**

```powershell
cd web
npm.cmd test -- scripts/readme-demo.test.mjs scripts/sync-demo-media.test.mjs
npm.cmd run build
```

Expected: tests PASS; build exits 0; `web/dist/demo/` contains the video, poster, checksum, and manifest.

- [ ] **Step 7: Commit Task 4**

```powershell
cd ..
git add README.md docs/images/workbench/freshsense-demo-thumbnail.png web/scripts/readme-demo.test.mjs
git commit -m "Feature public demo in FreshSense README"
```

---

### Task 5: Validate in browsers, deploy to Azure, and publish

**Files:**
- Modify only if verification finds a defect: files introduced in Tasks 1–4
- Deployment output: existing Azure Static Web App `freshsense-web-8548`

**Interfaces:**
- Consumes: `web/dist`, Azure Static Web Apps deployment token, custom domain `freshsenseai.com`
- Produces: public `https://freshsenseai.com/demo`

- [ ] **Step 1: Run the complete local regression suite**

```powershell
py -3.11 -m pytest -q tests --basetemp "$env:TEMP\freshsense-public-demo-tests"
cd web
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
cd ..\video
npm.cmd test
npm.cmd run typecheck
npm.cmd run verify
```

Expected: 189 Python tests, all web tests, all video tests, both TypeScript checks,
the web production build, and the MP4 contract PASS.

- [ ] **Step 2: Run the local production preview and browser checks**

Start the preview without opening a visible terminal window:

```powershell
cd web
Start-Process -FilePath "npm.cmd" -ArgumentList "run","preview","--","--host","localhost","--port","4173" -WorkingDirectory (Get-Location) -WindowStyle Hidden
```

Open `http://localhost:4173/demo` in the in-app browser and verify:

- HTTP page loads without a Microsoft login redirect;
- video is muted and attempting autoplay;
- native controls and poster are present;
- `Enable sound` unmutes and playback continues;
- mobile-width layout remains readable;
- all three actions and safety copy are visible;
- `/` still reaches the authenticated FreshSense application.

- [ ] **Step 3: Refresh Azure authentication without exposing credentials**

Run:

```powershell
az login --tenant "9899df57-c16f-41e9-b872-70cadda37ab7" --scope "https://management.core.windows.net//.default"
az account set --subscription "764231f6-a55f-4229-88d6-e1920bd10b58"
az account show --query "{tenantId:tenantId,subscription:id,user:user.name}" -o json
```

Expected: tenant `9899df57-c16f-41e9-b872-70cadda37ab7`, subscription
`764231f6-a55f-4229-88d6-e1920bd10b58`, and the intended administrator account.

- [ ] **Step 4: Deploy the verified static build**

Retrieve the token only into process memory and deploy with the pinned CLI:

```powershell
$deploymentToken = az staticwebapp secrets list `
  --name "freshsense-web-8548" `
  --resource-group "freshsense-staging-rg" `
  --query "properties.apiKey" -o tsv
if (-not $deploymentToken) { throw "Azure Static Web Apps deployment token is unavailable." }
npx.cmd --yes @azure/static-web-apps-cli@2.0.10 deploy web\dist `
  --deployment-token $deploymentToken `
  --env production
Remove-Variable deploymentToken
```

Never print, commit, or write the deployment token to disk.

- [ ] **Step 5: Verify the deployed custom-domain experience**

Check network responses:

```powershell
$demo = Invoke-WebRequest -Uri "https://freshsenseai.com/demo" -UseBasicParsing
if ($demo.StatusCode -ne 200) { throw "Public demo route did not return HTTP 200." }
$video = Invoke-WebRequest -Uri "https://freshsenseai.com/demo/freshsense-recruiter-demo-60s.mp4" -Method Head -UseBasicParsing
if ($video.StatusCode -ne 200) { throw "Deployed demo video did not return HTTP 200." }
```

Open `https://freshsenseai.com/demo` in the in-app browser and repeat the no-login,
muted autoplay, sound, controls, poster, responsive, and fallback-link checks.

- [ ] **Step 6: Review, commit any verification fix, and publish through GitHub**

```powershell
git diff --check
git status -sb
git push -u origin agent/public-demo-page
gh pr create --draft --base main --head agent/public-demo-page `
  --title "Add public FreshSense video demo" `
  --body "Adds a no-login /demo player, deterministic media packaging, a clickable README poster, tests, and Azure deployment verification."
```

After GitHub checks pass, mark the PR ready and merge with a merge commit:

```powershell
gh pr ready
gh pr checks --watch
gh pr merge --merge --delete-branch
git switch main
git pull --ff-only origin main
```

Expected: remote and local `main` point to the merged public-demo delivery; the
README poster opens the already-verified `https://freshsenseai.com/demo` route.
