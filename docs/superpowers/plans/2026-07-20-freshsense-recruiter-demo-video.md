# FreshSense Recruiter Demo Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a 60-second Remotion product documentary for recruiters and AI Engineer interviewers, using the real FreshSense interface, English narration, timed English captions, and a public-project call to action.

**Architecture:** A separate `video/` workspace owns the timeline, visual components, generated audio, caption data, and render scripts. Typed scene data drives all Remotion sequences. Small Node and PowerShell tools copy existing screenshots, generate local narration and original ambient audio, transcribe the finished narration, render keyframes, and verify the final MP4 without changing the FreshSense product application.

**Tech Stack:** Remotion 4.0.495, React 19.2.7, TypeScript 5.9.3, Vitest 4.1.10, `@remotion/media`, `@remotion/captions`, Whisper.cpp, Windows System.Speech, FFmpeg through the Remotion CLI, Node.js 24.

## Global Constraints

- Output is 1920 by 1080, 30 FPS, H.264 with `yuv420p`, and between 58 and 62 seconds.
- The final file is `docs/demo/freshsense-recruiter-demo-60s.mp4`.
- Use the real screenshots already stored in `docs/images/workbench/`; do not fabricate UI, values, customer data, or product features.
- Keep key text at least 80 pixels from the sides and 100 pixels from the top and bottom.
- Use FreshSense green, warm white, and charcoal; motion is limited to slow pans, slow zooms, opacity fades, and fine-line callouts.
- Drive every animation with `useCurrentFrame()` and `interpolate()`; CSS transitions, CSS animations, and Tailwind animation classes are forbidden.
- Narration is calm, neutral English. Captions are derived from the final narration file and stay within two lines.
- Uploaded-photo privacy, supported-input rejection, human review, and manager approval boundaries remain explicit.
- Do not modify product code or redeploy `freshsenseai.com`.
- A missing screenshot, narration, caption file, audio stream, or invalid duration must fail the build.
- If the installed Microsoft voice is not natural enough after preview, stop before the full render. Do not commit a silent or robotic placeholder.
- Keep all `remotion` and `@remotion/*` packages pinned to the same exact version, `4.0.495`, as required by the official package guidance.

---

## File map

| File | Responsibility |
| --- | --- |
| `video/package.json` | Exact dependencies and local build commands |
| `video/tsconfig.json` | Strict TypeScript configuration for source, tests, and scripts |
| `video/vitest.config.ts` | Node-based unit-test configuration |
| `video/remotion.config.ts` | H.264 and overwrite render defaults |
| `video/src/content.ts` | One source of truth for scene timing, narration, screenshots, and callouts |
| `video/src/timeline.ts` | Timeline validation and scene lookup |
| `video/src/theme.ts` | Colors, typography, spacing, and safe-area constants |
| `video/src/motion.ts` | Pure frame-to-style calculations |
| `video/src/components/*.tsx` | Reusable title, screenshot, callout, caption, stack, and closing visuals |
| `video/src/FreshSenseDemo.tsx` | Complete 60-second composition and audio layers |
| `video/src/Root.tsx` | Remotion composition registration |
| `video/src/index.ts` | Remotion entry point |
| `video/scripts/sync-assets.ts` | Copies approved screenshots into `video/public/screens/` |
| `video/scripts/generate-voiceover.ps1` | Generates local narration through Windows System.Speech |
| `video/scripts/generate-voiceover.ts` | Exports the approved copy and invokes the PowerShell voice generator |
| `video/scripts/generate-captions.ts` | Converts narration to 16 kHz, transcribes it, and writes Caption JSON |
| `video/scripts/generate-music.ts` | Produces a quiet original ambient WAV with FFmpeg filters |
| `video/scripts/render-stills.ts` | Renders the five required visual-review frames |
| `video/scripts/verify-output.ts` | Uses ffprobe to enforce final media requirements |
| `video/tests/*.test.ts` | Timeline, asset, caption, motion, and media validation tests |
| `.gitignore` | Excludes dependencies, temporary copies, Whisper binaries, and preview output |
| `README.md` | Links the new recruiter demo while keeping the existing project structure |

### Task 1: Create the deterministic video workspace and timeline

**Files:**
- Create: `video/package.json`
- Create: `video/tsconfig.json`
- Create: `video/vitest.config.ts`
- Create: `video/remotion.config.ts`
- Create: `video/src/content.ts`
- Create: `video/src/timeline.ts`
- Test: `video/tests/timeline.test.ts`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `SCENES: readonly Scene[]`, `TOTAL_FRAMES: 1800`, `NARRATION_TEXT: string`, `validateTimeline(scenes): string[]`, and `sceneAtFrame(frame): Scene`.
- Consumes: approved design timings from `docs/superpowers/specs/2026-07-20-freshsense-recruiter-demo-video-design.md`.

- [ ] **Step 1: Add the isolated package and strict TypeScript configuration**

Create `video/package.json` with exact versions and scripts:

```json
{
  "name": "freshsense-recruiter-demo",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "assets": "tsx scripts/sync-assets.ts",
    "voice": "tsx scripts/generate-voiceover.ts",
    "captions": "tsx scripts/generate-captions.ts",
    "music": "tsx scripts/generate-music.ts",
    "media": "npm run voice && npm run captions && npm run music",
    "test": "vitest run",
    "typecheck": "tsc --noEmit",
    "studio": "npm run assets && remotion studio src/index.ts",
    "render:stills": "npm run assets && tsx scripts/render-stills.ts",
    "render": "npm run assets && remotion render src/index.ts FreshSenseRecruiterDemo ../docs/demo/freshsense-recruiter-demo-60s.mp4 --codec=h264 --pixel-format=yuv420p --overwrite",
    "verify": "tsx scripts/verify-output.ts"
  },
  "dependencies": {
    "@remotion/captions": "4.0.495",
    "@remotion/install-whisper-cpp": "4.0.495",
    "@remotion/media": "4.0.495",
    "mediabunny": "1.50.9",
    "react": "19.2.7",
    "react-dom": "19.2.7",
    "remotion": "4.0.495"
  },
  "devDependencies": {
    "@remotion/cli": "4.0.495",
    "@types/node": "26.1.1",
    "@types/react": "19.2.17",
    "tsx": "4.23.1",
    "typescript": "5.9.3",
    "vitest": "4.1.10"
  }
}
```

Create `video/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["node", "vitest/globals"]
  },
  "include": ["src", "scripts", "tests", "remotion.config.ts", "vitest.config.ts"]
}
```

Create `video/vitest.config.ts`:

```ts
import {defineConfig} from 'vitest/config';

export default defineConfig({
  test: {environment: 'node', include: ['tests/**/*.test.ts']},
});
```

Create `video/remotion.config.ts`:

```ts
import {Config} from '@remotion/cli/config';

Config.setCodec('h264');
Config.setPixelFormat('yuv420p');
Config.setOverwriteOutput(true);
```

Append these exact entries to `.gitignore`:

```gitignore
video/node_modules/
video/out/
video/.tmp/
video/whisper.cpp/
video/public/screens/*.png
video/public/audio/*.wav
video/public/captions/*.json
```

- [ ] **Step 2: Write the failing timeline tests**

Create `video/tests/timeline.test.ts`:

```ts
import {describe, expect, it} from 'vitest';
import {NARRATION_TEXT, SCENES, TOTAL_FRAMES} from '../src/content';
import {sceneAtFrame, validateTimeline} from '../src/timeline';

describe('FreshSense timeline', () => {
  it('covers exactly 60 seconds at 30 fps without gaps', () => {
    expect(TOTAL_FRAMES).toBe(1800);
    expect(validateTimeline(SCENES)).toEqual([]);
    expect(SCENES.at(-1)?.endFrame).toBe(TOTAL_FRAMES);
  });

  it('keeps the approved eight story beats', () => {
    expect(SCENES.map((scene) => scene.id)).toEqual([
      'problem', 'overview', 'batch', 'vision', 'agent', 'review', 'manager', 'cta',
    ]);
  });

  it('keeps the 138-word approved narration', () => {
    expect(NARRATION_TEXT.trim().split(/\s+/)).toHaveLength(138);
  });

  it('resolves boundary frames to the correct scene', () => {
    expect(sceneAtFrame(0).id).toBe('problem');
    expect(sceneAtFrame(149).id).toBe('problem');
    expect(sceneAtFrame(150).id).toBe('overview');
    expect(sceneAtFrame(1799).id).toBe('cta');
  });
});
```

- [ ] **Step 3: Run the tests and verify the expected failure**

Run:

```powershell
cd video
npm.cmd install
npm.cmd test -- timeline.test.ts
```

Expected: FAIL because `src/content.ts` and `src/timeline.ts` do not exist.

- [ ] **Step 4: Implement the scene data and validation**

Create `video/src/content.ts` with these public types and values:

```ts
export const FPS = 30;
export const TOTAL_FRAMES = 60 * FPS;

export type Callout = {label: string; x: number; y: number; delayFrame: number};
export type SceneKind = 'title' | 'screenshot' | 'manager' | 'closing';
export type Scene = {
  id: string;
  kind: SceneKind;
  startFrame: number;
  endFrame: number;
  screenshot?: string;
  headline: string;
  narration: string;
  callouts: readonly Callout[];
};

export const SCENES: readonly Scene[] = [
  {id: 'problem', kind: 'title', startFrame: 0, endFrame: 150, headline: 'Fruit checks happen fast', narration: 'Fruit checks happen fast, but the record often disappears with the shift.', callouts: []},
  {id: 'overview', kind: 'screenshot', startFrame: 150, endFrame: 360, screenshot: 'overview.png', headline: 'One shared inspection workspace', narration: 'FreshSense gives small grocery teams one place to inspect fruit and follow review work.', callouts: [{label: 'Live inspection history', x: 73, y: 45, delayFrame: 40}]},
  {id: 'batch', kind: 'screenshot', startFrame: 360, endFrame: 690, screenshot: 'batch-inspection.png', headline: 'Inspect a batch in one step', narration: 'Staff can take a photo or add twenty images at once. The model covers apples, bananas, oranges, mangoes, tomatoes, and pears. Photos are not stored by default.', callouts: [{label: 'Camera or multi-photo upload', x: 36, y: 68, delayFrame: 45}, {label: 'Up to 20 images', x: 47, y: 58, delayFrame: 100}]},
  {id: 'vision', kind: 'screenshot', startFrame: 690, endFrame: 990, screenshot: 'batch-inspection.png', headline: 'Classify, or withhold', narration: 'A DenseNet201 classifier looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs instead of forcing a label.', callouts: [{label: 'DenseNet201 result', x: 73, y: 28, delayFrame: 40}, {label: 'Uncertain inputs are withheld', x: 73, y: 52, delayFrame: 110}]},
  {id: 'agent', kind: 'screenshot', startFrame: 990, endFrame: 1290, screenshot: 'agent-activity.png', headline: 'A bounded Agent follows through', narration: 'Next, a bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval.', callouts: [{label: 'Automatic follow-up tasks', x: 44, y: 31, delayFrame: 45}, {label: 'Manager approval boundary', x: 70, y: 31, delayFrame: 115}]},
  {id: 'review', kind: 'screenshot', startFrame: 1290, endFrame: 1500, screenshot: 'review-queue.png', headline: 'People make the final call', narration: 'Staff confirm or correct results in the review queue.', callouts: [{label: 'Human-observed outcome', x: 72, y: 42, delayFrame: 45}]},
  {id: 'manager', kind: 'manager', startFrame: 1500, endFrame: 1680, screenshot: 'manager-chat.png', headline: 'Grounded answers, daily evidence', narration: 'Managers ask grounded questions about inspection history and Agent decisions, then check the daily report.', callouts: [{label: 'Workspace citations', x: 61, y: 56, delayFrame: 30}]},
  {id: 'cta', kind: 'closing', startFrame: 1680, endFrame: 1800, headline: 'See FreshSense working', narration: 'FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try freshsenseai.com, or view the code on GitHub.', callouts: []},
] as const;

export const NARRATION_TEXT = SCENES.map((scene) => scene.narration).join(' ');
```

Create `video/src/timeline.ts`:

```ts
import {SCENES, TOTAL_FRAMES, type Scene} from './content';

export const validateTimeline = (scenes: readonly Scene[]): string[] => {
  const errors: string[] = [];
  if (scenes.length === 0) return ['timeline has no scenes'];
  if (scenes[0].startFrame !== 0) errors.push('timeline must start at frame 0');
  scenes.forEach((scene, index) => {
    if (scene.endFrame <= scene.startFrame) errors.push(`${scene.id} has no duration`);
    if (index > 0 && scenes[index - 1].endFrame !== scene.startFrame) {
      errors.push(`${scene.id} does not touch the previous scene`);
    }
  });
  if (scenes.at(-1)?.endFrame !== TOTAL_FRAMES) errors.push('timeline must end at frame 1800');
  return errors;
};

export const sceneAtFrame = (frame: number): Scene => {
  const scene = SCENES.find((item) => frame >= item.startFrame && frame < item.endFrame);
  if (!scene) throw new Error(`No scene covers frame ${frame}`);
  return scene;
};
```

- [ ] **Step 5: Run tests and type checking**

Run:

```powershell
npm.cmd test -- timeline.test.ts
npm.cmd run typecheck
```

Expected: four passing timeline tests and TypeScript exit code 0.

- [ ] **Step 6: Commit the workspace foundation**

```powershell
git add .gitignore video/package.json video/package-lock.json video/tsconfig.json video/vitest.config.ts video/remotion.config.ts video/src/content.ts video/src/timeline.ts video/tests/timeline.test.ts
git commit -m "Build FreshSense video timeline foundation"
```

### Task 2: Synchronize and validate the approved screenshots

**Files:**
- Create: `video/src/assets.ts`
- Create: `video/scripts/sync-assets.ts`
- Create: `video/public/screens/.gitkeep`
- Create: `video/public/audio/.gitkeep`
- Create: `video/public/captions/.gitkeep`
- Test: `video/tests/assets.test.ts`

**Interfaces:**
- Consumes: `SCENES` screenshot filenames.
- Produces: `REQUIRED_SCREENS`, `readPngDimensions(path)`, and `syncScreens(repoRoot, videoRoot)`.

- [ ] **Step 1: Write failing asset tests**

Create `video/tests/assets.test.ts`:

```ts
import {mkdtempSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {describe, expect, it} from 'vitest';
import {readPngDimensions, syncScreens} from '../scripts/sync-assets';

const pngHeader = (width: number, height: number) => {
  const data = Buffer.alloc(24);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(data, 0);
  data.writeUInt32BE(width, 16);
  data.writeUInt32BE(height, 20);
  return data;
};

describe('approved screenshot assets', () => {
  it('reads PNG dimensions from the IHDR header', () => {
    const root = mkdtempSync(join(tmpdir(), 'freshsense-png-'));
    const file = join(root, 'screen.png');
    writeFileSync(file, pngHeader(1920, 1080));
    expect(readPngDimensions(file)).toEqual({width: 1920, height: 1080});
  });

  it('copies every required screen into the Remotion public folder', () => {
    const root = mkdtempSync(join(tmpdir(), 'freshsense-assets-'));
    const repo = join(root, 'repo');
    const video = join(repo, 'video');
    mkdirSync(join(repo, 'docs', 'images', 'workbench'), {recursive: true});
    for (const name of ['overview.png', 'batch-inspection.png', 'review-queue.png', 'agent-activity.png', 'manager-chat.png', 'daily-report.png']) {
      writeFileSync(join(repo, 'docs', 'images', 'workbench', name), pngHeader(1920, 1080));
    }
    syncScreens(repo, video);
    expect(readFileSync(join(video, 'public', 'screens', 'manager-chat.png'))).toEqual(pngHeader(1920, 1080));
  });
});
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run: `npm.cmd test -- assets.test.ts`

Expected: FAIL because `scripts/sync-assets.ts` does not exist.

- [ ] **Step 3: Implement the manifest and strict copy operation**

Create `video/src/assets.ts`:

```ts
export const REQUIRED_SCREENS = [
  'overview.png',
  'batch-inspection.png',
  'review-queue.png',
  'agent-activity.png',
  'manager-chat.png',
  'daily-report.png',
] as const;
```

Create `video/scripts/sync-assets.ts`:

```ts
import {copyFileSync, existsSync, mkdirSync, readFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {REQUIRED_SCREENS} from '../src/assets';

export const readPngDimensions = (path: string) => {
  const header = readFileSync(path).subarray(0, 24);
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (header.length < 24 || !header.subarray(0, 8).equals(signature)) throw new Error(`${path} is not a PNG`);
  return {width: header.readUInt32BE(16), height: header.readUInt32BE(20)};
};

export const syncScreens = (repoRoot: string, videoRoot: string) => {
  const sourceRoot = join(repoRoot, 'docs', 'images', 'workbench');
  const destinationRoot = join(videoRoot, 'public', 'screens');
  mkdirSync(destinationRoot, {recursive: true});
  for (const name of REQUIRED_SCREENS) {
    const source = join(sourceRoot, name);
    if (!existsSync(source)) throw new Error(`Missing approved screenshot: ${source}`);
    const dimensions = readPngDimensions(source);
    if (dimensions.width < 1900 || dimensions.height < 1000) throw new Error(`${name} is too small for a 1080p crop`);
    copyFileSync(source, join(destinationRoot, name));
  }
};

if (resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  syncScreens(resolve(videoRoot, '..'), videoRoot);
  console.log(`Copied ${REQUIRED_SCREENS.length} approved screenshots.`);
}
```

Create the three `.gitkeep` files so the required public directories exist in a fresh checkout.

- [ ] **Step 4: Run the unit tests and real asset sync**

Run:

```powershell
npm.cmd test -- assets.test.ts
npm.cmd run assets
Get-ChildItem public\screens\*.png | Select-Object Name,Length
```

Expected: two passing tests, six PNG files, and no file smaller than 50 KB.

- [ ] **Step 5: Commit asset synchronization**

```powershell
git add video/src/assets.ts video/scripts/sync-assets.ts video/public/screens/.gitkeep video/public/audio/.gitkeep video/public/captions/.gitkeep video/tests/assets.test.ts
git commit -m "Validate FreshSense video screenshots"
```

### Task 3: Build the video-first visual components

**Files:**
- Create: `video/src/theme.ts`
- Create: `video/src/motion.ts`
- Create: `video/src/components/TitleCard.tsx`
- Create: `video/src/components/ScreenshotScene.tsx`
- Create: `video/src/components/Callout.tsx`
- Create: `video/src/components/CaptionTrack.tsx`
- Create: `video/src/components/TechStack.tsx`
- Create: `video/src/components/ClosingCard.tsx`
- Test: `video/tests/motion.test.ts`

**Interfaces:**
- Consumes: `Scene`, `Callout`, approved screenshots, and Remotion `Caption[]` JSON.
- Produces: `getScreenshotMotion(frame, duration)`, `TitleCard`, `ScreenshotScene`, `CaptionTrack`, and `ClosingCard`.

- [ ] **Step 1: Write failing motion tests**

Create `video/tests/motion.test.ts`:

```ts
import {describe, expect, it} from 'vitest';
import {getScreenshotMotion} from '../src/motion';

describe('documentary screenshot motion', () => {
  it('starts at full size and ends with a restrained zoom', () => {
    expect(getScreenshotMotion(0, 300)).toEqual({scale: 1, x: 0, opacity: 0});
    const end = getScreenshotMotion(299, 300);
    expect(end.scale).toBeGreaterThan(1.035);
    expect(end.scale).toBeLessThanOrEqual(1.04);
    expect(end.opacity).toBeLessThan(0.1);
  });

  it('is fully visible through the middle of a scene', () => {
    expect(getScreenshotMotion(150, 300).opacity).toBe(1);
  });
});
```

- [ ] **Step 2: Run the motion test and verify failure**

Run: `npm.cmd test -- motion.test.ts`

Expected: FAIL because `src/motion.ts` is missing.

- [ ] **Step 3: Implement theme and deterministic motion**

Create `video/src/theme.ts`:

```ts
export const theme = {
  green: '#2F9E55',
  greenDark: '#176B3A',
  greenSoft: '#EAF6EE',
  warmWhite: '#FAF9F5',
  charcoal: '#202521',
  muted: '#5E685F',
  line: '#D8DED8',
  warning: '#A45C10',
  safeX: 112,
  safeY: 100,
  font: 'Arial, Helvetica, sans-serif',
} as const;
```

Create `video/src/motion.ts`:

```ts
import {Easing, interpolate} from 'remotion';

export const getScreenshotMotion = (frame: number, duration: number) => ({
  scale: interpolate(frame, [0, duration - 1], [1, 1.04], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.55, 1)}),
  x: interpolate(frame, [0, duration - 1], [0, -18], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.55, 1)}),
  opacity: interpolate(frame, [0, 15, duration - 16, duration - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
});
```

- [ ] **Step 4: Implement the reusable visual components**

Use these exact public signatures:

```tsx
// components/Callout.tsx
import {interpolate, useCurrentFrame} from 'remotion';
import type {Callout as CalloutData} from '../content';
import {theme} from '../theme';

export const Callout: React.FC<{data: CalloutData}> = ({data}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [data.delayFrame, data.delayFrame + 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div style={{position: 'absolute', left: `${data.x}%`, top: `${data.y}%`, display: 'flex', alignItems: 'center', gap: 12, color: theme.charcoal, font: `700 34px ${theme.font}`, opacity: progress, translate: `${16 * (1 - progress)}px 0`}}>
    <span style={{width: 14, height: 14, borderRadius: 7, background: theme.green}} />
    <span style={{background: 'rgba(250,249,245,0.94)', border: `2px solid ${theme.green}`, borderRadius: 8, padding: '12px 18px'}}>{data.label}</span>
  </div>;
};
```

```tsx
// components/TitleCard.tsx
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {theme} from '../theme';

export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{background: theme.warmWhite, justifyContent: 'center', alignItems: 'center', color: theme.charcoal}}>
    <div style={{width: 150, height: 8, background: theme.green, marginBottom: 36, opacity: interpolate(frame, [0, 20], [0, 1], {extrapolateRight: 'clamp'})}} />
    <h1 style={{font: `700 112px ${theme.font}`, margin: 0, opacity: interpolate(frame, [10, 42], [0, 1], {extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)})}}>FreshSense</h1>
    <p style={{font: `400 46px ${theme.font}`, color: theme.muted, margin: '28px 0 0'}}>AI-assisted fruit inspection for small grocery teams</p>
  </AbsoluteFill>;
};
```

```tsx
// components/ScreenshotScene.tsx
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import type {Scene} from '../content';
import {getScreenshotMotion} from '../motion';
import {theme} from '../theme';
import {Callout} from './Callout';

export const ScreenshotScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const duration = scene.endFrame - scene.startFrame;
  const motion = getScreenshotMotion(frame, duration);
  if (!scene.screenshot) throw new Error(`${scene.id} has no screenshot`);
  return <AbsoluteFill style={{background: theme.warmWhite, padding: `${theme.safeY}px ${theme.safeX}px`}}>
    <div style={{font: `700 68px ${theme.font}`, color: theme.charcoal, marginBottom: 24}}>{scene.headline}</div>
    <div style={{position: 'relative', flex: 1, overflow: 'hidden', borderRadius: 18, border: `1px solid ${theme.line}`, boxShadow: '0 18px 50px rgba(32,37,33,0.12)', opacity: motion.opacity}}>
      <Img src={staticFile(`screens/${scene.screenshot}`)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center', scale: motion.scale, translate: `${motion.x}px 0`}} />
      {scene.callouts.map((item) => <Callout key={item.label} data={item} />)}
    </div>
  </AbsoluteFill>;
};
```

```tsx
// components/TechStack.tsx
import {theme} from '../theme';

const technologies = ['Python', 'TensorFlow', 'FastAPI', 'React', 'PostgreSQL', 'Azure'];
export const TechStack: React.FC = () => <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 18}}>
  {technologies.map((name) => <span key={name} style={{font: `600 36px ${theme.font}`, color: theme.greenDark, border: `2px solid ${theme.green}`, borderRadius: 999, padding: '12px 22px'}}>{name}</span>)}
</div>;
```

```tsx
// components/ClosingCard.tsx
import {AbsoluteFill} from 'remotion';
import {theme} from '../theme';
import {TechStack} from './TechStack';

export const ClosingCard: React.FC = () => <AbsoluteFill style={{background: theme.warmWhite, justifyContent: 'center', alignItems: 'center', color: theme.charcoal, gap: 36}}>
  <h1 style={{font: `700 86px ${theme.font}`, margin: 0}}>See FreshSense working</h1>
  <TechStack />
  <div style={{display: 'flex', gap: 56, font: `700 36px ${theme.font}`, color: theme.greenDark}}>
    <span>freshsenseai.com</span><span>github.com/yyq8548/FreshSenseAI--app</span>
  </div>
</AbsoluteFill>;
```

Create `video/src/components/CaptionTrack.tsx`:

```tsx
import {createTikTokStyleCaptions, type Caption} from '@remotion/captions';
import {useMemo} from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {theme} from '../theme';

export const CaptionTrack: React.FC<{captions: readonly Caption[]}> = ({captions}) => {
  const {fps} = useVideoConfig();
  const {pages} = useMemo(() => createTikTokStyleCaptions({
    captions: [...captions],
    combineTokensWithinMilliseconds: 1800,
  }), [captions]);

  return <AbsoluteFill style={{pointerEvents: 'none'}}>
    {pages.map((page, index) => {
      const next = pages[index + 1];
      const from = Math.round(page.startMs / 1000 * fps);
      const end = Math.round(Math.min(next?.startMs ?? 60000, page.startMs + 1800) / 1000 * fps);
      return <Sequence key={`${page.startMs}-${index}`} from={from} durationInFrames={Math.max(1, end - from)}>
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', padding: `0 ${theme.safeX + 100}px 110px`}}>
          <div style={{maxWidth: 1460, borderRadius: 12, padding: '14px 24px', background: 'rgba(32,37,33,0.92)', color: '#FFFFFF', font: `600 42px/1.25 ${theme.font}`, textAlign: 'center', whiteSpace: 'pre-wrap'}}>
            {page.tokens.map((token) => token.text).join('')}
          </div>
        </AbsoluteFill>
      </Sequence>;
    })}
  </AbsoluteFill>;
};
```

- [ ] **Step 5: Run visual-unit tests and type checking**

Run:

```powershell
npm.cmd test -- motion.test.ts
npm.cmd run typecheck
```

Expected: two passing motion tests and TypeScript exit code 0.

- [ ] **Step 6: Commit the visual system**

```powershell
git add video/src/theme.ts video/src/motion.ts video/src/components video/tests/motion.test.ts
git commit -m "Create FreshSense documentary video components"
```

### Task 4: Generate narration, captions, and original ambient audio

**Files:**
- Create: `video/scripts/generate-voiceover.ps1`
- Create: `video/scripts/generate-voiceover.ts`
- Create: `video/scripts/generate-captions.ts`
- Create: `video/scripts/generate-music.ts`
- Create: `video/src/media.ts`
- Test: `video/tests/media.test.ts`

**Interfaces:**
- Consumes: `NARRATION_TEXT` and the Windows voice named by `FRESHSENSE_DEMO_VOICE`, default `Microsoft Zira Desktop`.
- Produces: `public/audio/narration.wav`, `public/audio/ambient.wav`, `public/captions/narration.json`, and `validateCaptions(captions): string[]`.

- [ ] **Step 1: Write failing caption validation tests**

Create `video/tests/media.test.ts`:

```ts
import type {Caption} from '@remotion/captions';
import {describe, expect, it} from 'vitest';
import {validateCaptions} from '../src/media';

const caption = (text: string, startMs: number, endMs: number): Caption => ({text, startMs, endMs, timestampMs: null, confidence: 1});

describe('caption validation', () => {
  it('accepts ordered non-overlapping captions inside 60 seconds', () => {
    expect(validateCaptions([caption(' Fruit checks happen fast.', 200, 1800), caption(' FreshSense records the work.', 1900, 3500)])).toEqual([]);
  });

  it('rejects overlap and captions beyond the composition', () => {
    expect(validateCaptions([caption(' one', 0, 2000), caption(' two', 1900, 61000)])).toEqual([
      'caption 1 overlaps caption 0',
      'caption 1 ends after the composition',
    ]);
  });
});
```

- [ ] **Step 2: Run the media test and verify failure**

Run: `npm.cmd test -- media.test.ts`

Expected: FAIL because `src/media.ts` is missing.

- [ ] **Step 3: Implement caption validation**

Create `video/src/media.ts`:

```ts
import type {Caption} from '@remotion/captions';

export const validateCaptions = (captions: readonly Caption[]): string[] => {
  const errors: string[] = [];
  captions.forEach((caption, index) => {
    if (caption.endMs <= caption.startMs) errors.push(`caption ${index} has no duration`);
    if (index > 0 && caption.startMs < captions[index - 1].endMs) errors.push(`caption ${index} overlaps caption ${index - 1}`);
    if (caption.endMs > 60000) errors.push(`caption ${index} ends after the composition`);
  });
  return errors;
};
```

- [ ] **Step 4: Add local English voice generation**

Create `video/scripts/generate-voiceover.ps1`:

```powershell
param(
  [Parameter(Mandatory=$true)][string]$TextPath,
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [string]$VoiceName = 'Microsoft Zira Desktop'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
  $installed = $speaker.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }
  if ($installed -notcontains $VoiceName) { throw "Required voice is not installed: $VoiceName" }
  $speaker.SelectVoice($VoiceName)
  $speaker.Rate = 0
  $speaker.Volume = 100
  $speaker.SetOutputToWaveFile($OutputPath)
  $speaker.Speak((Get-Content -LiteralPath $TextPath -Raw))
} finally {
  $speaker.Dispose()
}
```

Create `video/scripts/generate-voiceover.ts`:

```ts
import {execFileSync} from 'node:child_process';
import {mkdirSync, statSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {NARRATION_TEXT} from '../src/content';

const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tempRoot = join(videoRoot, '.tmp');
const audioRoot = join(videoRoot, 'public', 'audio');
const textPath = join(tempRoot, 'narration.txt');
const outputPath = join(audioRoot, 'narration.wav');
const scriptPath = join(videoRoot, 'scripts', 'generate-voiceover.ps1');
const voice = process.env.FRESHSENSE_DEMO_VOICE ?? 'Microsoft Zira Desktop';

mkdirSync(tempRoot, {recursive: true});
mkdirSync(audioRoot, {recursive: true});
writeFileSync(textPath, NARRATION_TEXT, 'utf8');
execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath, '-TextPath', textPath, '-OutputPath', outputPath, '-VoiceName', voice], {stdio: 'inherit'});
if (statSync(outputPath).size <= 100_000) throw new Error('Narration output is missing or too small.');
console.log(`Generated narration with ${voice}: ${outputPath}`);
```

- [ ] **Step 5: Generate captions from the finished voice file**

Create `video/scripts/generate-captions.ts`:

```ts
import {execFileSync} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {downloadWhisperModel, installWhisperCpp, toCaptions, transcribe} from '@remotion/install-whisper-cpp';
import {validateCaptions} from '../src/media';

const whisperVersion = '1.5.5';
const whisperModel = 'small.en' as const;
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const whisperRoot = join(videoRoot, 'whisper.cpp');
const tempRoot = join(videoRoot, '.tmp');
const captionRoot = join(videoRoot, 'public', 'captions');
const input = join(videoRoot, 'public', 'audio', 'narration.wav');
const converted = join(tempRoot, 'narration-16k.wav');

mkdirSync(tempRoot, {recursive: true});
mkdirSync(captionRoot, {recursive: true});
execFileSync(npx, ['remotion', 'ffmpeg', '-i', input, '-ar', '16000', '-ac', '1', converted, '-y'], {stdio: 'inherit'});
await installWhisperCpp({to: whisperRoot, version: whisperVersion});
await downloadWhisperModel({model: whisperModel, folder: whisperRoot});
const whisperCppOutput = await transcribe({
  model: whisperModel,
  whisperPath: whisperRoot,
  whisperCppVersion: whisperVersion,
  inputPath: converted,
  tokenLevelTimestamps: true,
});
const {captions} = toCaptions({whisperCppOutput});
const errors = validateCaptions(captions);
if (errors.length > 0) throw new Error(errors.join('\n'));
writeFileSync(join(captionRoot, 'narration.json'), `${JSON.stringify(captions, null, 2)}\n`, 'utf8');
console.log(`Generated ${captions.length} timed captions.`);
```

- [ ] **Step 6: Generate a quiet original music bed**

Create `video/scripts/generate-music.ts`:

```ts
import {execFileSync} from 'node:child_process';
import {mkdirSync, statSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const audioRoot = join(videoRoot, 'public', 'audio');
const output = join(audioRoot, 'ambient.wav');
mkdirSync(audioRoot, {recursive: true});
const source = 'aevalsrc=0.016*sin(2*PI*110*t)+0.010*sin(2*PI*164.81*t)+0.008*sin(2*PI*220*t):s=48000:d=60,lowpass=f=850,afade=t=in:st=0:d=2,afade=t=out:st=57:d=3';
execFileSync(npx, ['remotion', 'ffmpeg', '-f', 'lavfi', '-i', source, '-c:a', 'pcm_s16le', output, '-y'], {stdio: 'inherit'});
if (statSync(output).size <= 100_000) throw new Error('Ambient audio output is missing or too small.');
console.log(`Generated original ambient bed: ${output}`);
```

- [ ] **Step 7: Run tests, generate media, and perform the voice gate**

Run:

```powershell
npm.cmd test -- media.test.ts
npm.cmd run voice
npm.cmd run captions
npm.cmd run music
npx.cmd remotion ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 public/audio/narration.wav
```

Expected: two passing media tests, three generated files, narration shorter than 59.5 seconds, and captions ending before 60 seconds.

Listen to `video/public/audio/narration.wav`. Continue only if the voice sounds calm, neutral, understandable, and natural enough for a public portfolio. If it fails this review, stop and request an ElevenLabs voice key or another approved voice source.

- [ ] **Step 8: Commit the reproducible media pipeline**

Commit scripts and tests only. Generated WAV and JSON files remain ignored until the final accepted media commit.

```powershell
git add video/scripts/generate-voiceover.ps1 video/scripts/generate-voiceover.ts video/scripts/generate-captions.ts video/scripts/generate-music.ts video/src/media.ts video/tests/media.test.ts
git commit -m "Generate FreshSense video narration and captions"
```

### Task 5: Assemble the full Remotion composition and render review frames

**Files:**
- Create: `video/src/FreshSenseDemo.tsx`
- Create: `video/src/Root.tsx`
- Create: `video/src/index.ts`
- Create: `video/scripts/render-stills.ts`
- Test: `video/tests/composition.test.ts`

**Interfaces:**
- Consumes: `SCENES`, `TOTAL_FRAMES`, all visual components, `narration.wav`, `ambient.wav`, and `narration.json`.
- Produces: composition ID `FreshSenseRecruiterDemo` and five PNG review frames.

- [ ] **Step 1: Write the failing composition contract test**

Create `video/tests/composition.test.ts`:

```ts
import {describe, expect, it} from 'vitest';
import {SCENES, TOTAL_FRAMES} from '../src/content';

describe('composition contract', () => {
  it('uses one sequence per scene and the approved final duration', () => {
    expect(SCENES).toHaveLength(8);
    expect(SCENES.reduce((sum, scene) => sum + scene.endFrame - scene.startFrame, 0)).toBe(TOTAL_FRAMES);
  });

  it('uses only approved screenshots', () => {
    expect([...new Set(SCENES.flatMap((scene) => scene.screenshot ? [scene.screenshot] : []))]).toEqual([
      'overview.png', 'batch-inspection.png', 'agent-activity.png', 'review-queue.png', 'manager-chat.png',
    ]);
  });
});
```

- [ ] **Step 2: Run the contract test**

Run: `npm.cmd test -- composition.test.ts`

Expected: two passing tests. This test freezes the approved content contract before composition code is added.

- [ ] **Step 3: Register the composition**

Create `video/src/Root.tsx`:

```tsx
import {Composition} from 'remotion';
import {FreshSenseDemo} from './FreshSenseDemo';
import {FPS, TOTAL_FRAMES} from './content';

export const RemotionRoot: React.FC = () => <Composition
  id="FreshSenseRecruiterDemo"
  component={FreshSenseDemo}
  durationInFrames={TOTAL_FRAMES}
  fps={FPS}
  width={1920}
  height={1080}
  defaultProps={{captionFile: 'captions/narration.json'}}
/>;
```

Create `video/src/index.ts`:

```ts
import {registerRoot} from 'remotion';
import {RemotionRoot} from './Root';

registerRoot(RemotionRoot);
```

- [ ] **Step 4: Implement the complete composition**

Create `video/src/FreshSenseDemo.tsx`:

```tsx
import type {Caption} from '@remotion/captions';
import {Audio} from '@remotion/media';
import {useCallback, useEffect, useState} from 'react';
import {AbsoluteFill, Img, interpolate, Sequence, staticFile, useCurrentFrame, useDelayRender} from 'remotion';
import {CaptionTrack} from './components/CaptionTrack';
import {ClosingCard} from './components/ClosingCard';
import {ScreenshotScene} from './components/ScreenshotScene';
import {TitleCard} from './components/TitleCard';
import {SCENES, type Scene} from './content';
import {theme} from './theme';

const ManagerScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const switchOpacity = interpolate(frame, [90, 120], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: theme.warmWhite, padding: `${theme.safeY}px ${theme.safeX}px`}}>
    <div style={{font: `700 68px ${theme.font}`, color: theme.charcoal, marginBottom: 24}}>{scene.headline}</div>
    <div style={{position: 'relative', flex: 1, overflow: 'hidden', borderRadius: 18, border: `1px solid ${theme.line}`, boxShadow: '0 18px 50px rgba(32,37,33,0.12)'}}>
      <Img src={staticFile('screens/manager-chat.png')} style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', opacity: 1 - switchOpacity}} />
      <Img src={staticFile('screens/daily-report.png')} style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', opacity: switchOpacity}} />
    </div>
  </AbsoluteFill>;
};

const SceneRenderer: React.FC<{scene: Scene}> = ({scene}) => {
  if (scene.kind === 'title') return <TitleCard />;
  if (scene.kind === 'closing') return <ClosingCard />;
  if (scene.kind === 'manager') return <ManagerScene scene={scene} />;
  return <ScreenshotScene scene={scene} />;
};

export const FreshSenseDemo: React.FC<{captionFile: string}> = ({captionFile}) => {
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const {delayRender, continueRender, cancelRender} = useDelayRender();
  const [handle] = useState(() => delayRender('Loading FreshSense captions'));
  const loadCaptions = useCallback(async () => {
    try {
      const response = await fetch(staticFile(captionFile));
      if (!response.ok) throw new Error(`Caption request failed with ${response.status}`);
      setCaptions(await response.json() as Caption[]);
      continueRender(handle);
    } catch (error) {
      cancelRender(error instanceof Error ? error : new Error(String(error)));
    }
  }, [cancelRender, captionFile, continueRender, handle]);

  useEffect(() => { void loadCaptions(); }, [loadCaptions]);
  if (!captions) return null;

  return <AbsoluteFill style={{background: theme.warmWhite}}>
    <Audio src={staticFile('audio/narration.wav')} volume={1} />
    <Audio src={staticFile('audio/ambient.wav')} volume={0.10} />
    {SCENES.map((scene) => <Sequence key={scene.id} from={scene.startFrame} durationInFrames={scene.endFrame - scene.startFrame}>
      <SceneRenderer scene={scene} />
    </Sequence>)}
    <CaptionTrack captions={captions} />
  </AbsoluteFill>;
};
```

- [ ] **Step 5: Add deterministic still rendering**

Create `video/scripts/render-stills.ts`:

```ts
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import {resolve} from 'node:path';

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const frames = [0, 450, 900, 1350, 1770];
mkdirSync(resolve('out', 'stills'), {recursive: true});
for (const frame of frames) {
  execFileSync(npx, ['remotion', 'still', 'src/index.ts', 'FreshSenseRecruiterDemo', `out/stills/frame-${frame}.png`, '--frame', String(frame), '--overwrite'], {stdio: 'inherit'});
}
```

- [ ] **Step 6: Run all tests, type checking, and still renders**

Run:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run render:stills
```

Expected: all tests pass, TypeScript exits 0, and these files exist:

```text
video/out/stills/frame-0.png
video/out/stills/frame-450.png
video/out/stills/frame-900.png
video/out/stills/frame-1350.png
video/out/stills/frame-1770.png
```

Inspect all five with the image viewer. Confirm one focal point per frame, readable 42 pixel captions, no clipped callouts, real screenshot values, and title-safe placement. Fix the component, rerender that frame, and repeat until all five pass.

- [ ] **Step 7: Commit the composition**

```powershell
git add video/src/FreshSenseDemo.tsx video/src/Root.tsx video/src/index.ts video/scripts/render-stills.ts video/tests/composition.test.ts
git commit -m "Assemble FreshSense recruiter demo composition"
```

### Task 6: Render, verify, document, and package the demo

**Files:**
- Create: `video/scripts/verify-output.ts`
- Modify: `README.md`
- Create: `docs/demo/freshsense-recruiter-demo-60s.mp4`
- Test: `video/tests/output-validation.test.ts`

**Interfaces:**
- Consumes: complete Remotion composition and generated media.
- Produces: verified public MP4 plus README link.

- [ ] **Step 1: Write failing output-validation tests**

Create `video/tests/output-validation.test.ts`:

```ts
import {describe, expect, it} from 'vitest';
import {validateProbe} from '../scripts/verify-output';

describe('final MP4 validation', () => {
  it('accepts the required H.264 video and audio streams', () => {
    expect(validateProbe({format: {duration: '60.0'}, streams: [{codec_type: 'video', codec_name: 'h264', width: 1920, height: 1080, r_frame_rate: '30/1', pix_fmt: 'yuv420p'}, {codec_type: 'audio', codec_name: 'aac'}]})).toEqual([]);
  });

  it('rejects missing audio and an invalid duration', () => {
    expect(validateProbe({format: {duration: '70.0'}, streams: [{codec_type: 'video', codec_name: 'h264', width: 1920, height: 1080, r_frame_rate: '30/1', pix_fmt: 'yuv420p'}]})).toEqual(['duration must be between 58 and 62 seconds', 'audio stream is missing']);
  });
});
```

- [ ] **Step 2: Run the test and verify failure**

Run: `npm.cmd test -- output-validation.test.ts`

Expected: FAIL because `scripts/verify-output.ts` is missing.

- [ ] **Step 3: Implement ffprobe validation**

Create `video/scripts/verify-output.ts`:

```ts
import {execFileSync} from 'node:child_process';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

type ProbeStream = {codec_type?: string; codec_name?: string; width?: number; height?: number; r_frame_rate?: string; pix_fmt?: string};
export type ProbeResult = {format: {duration?: string}; streams: ProbeStream[]};

export const validateProbe = (probe: ProbeResult): string[] => {
  const errors: string[] = [];
  const duration = Number(probe.format.duration);
  const video = probe.streams.find((stream) => stream.codec_type === 'video');
  const audio = probe.streams.find((stream) => stream.codec_type === 'audio');
  if (duration < 58 || duration > 62) errors.push('duration must be between 58 and 62 seconds');
  if (!video) errors.push('video stream is missing');
  if (video && (video.codec_name !== 'h264' || video.width !== 1920 || video.height !== 1080 || video.r_frame_rate !== '30/1' || video.pix_fmt !== 'yuv420p')) errors.push('video stream does not match the 1080p H.264 contract');
  if (!audio) errors.push('audio stream is missing');
  return errors;
};

if (resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
  const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const output = resolve(videoRoot, '..', 'docs', 'demo', 'freshsense-recruiter-demo-60s.mp4');
  const stdout = execFileSync(npx, ['remotion', 'ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', output], {encoding: 'utf8'});
  const errors = validateProbe(JSON.parse(stdout) as ProbeResult);
  if (errors.length > 0) {
    for (const error of errors) console.error(error);
    process.exit(1);
  }
  console.log('FreshSense recruiter demo media contract passed.');
}
```

- [ ] **Step 4: Render and validate the MP4**

Run:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run render
npm.cmd run verify
```

Expected: all tests pass, type checking exits 0, the render completes, and verification prints `FreshSense recruiter demo media contract passed.`

- [ ] **Step 5: Watch the final video twice**

First watch with audio. Confirm the voice is clear, music never competes with narration, captions match spoken words, and every claim is accurate.

Second watch muted. Confirm the title, callouts, captions, safety boundary, URL, and GitHub repository still explain the workflow.

If any check fails, change the relevant source, rerender the affected still, rerender the MP4, and rerun `npm.cmd run verify`.

- [ ] **Step 6: Update the README demo link**

Replace:

```markdown
[Watch the 30-second Windows beta walkthrough](docs/demo/freshsense-public-beta-demo.mp4)
```

with:

```markdown
[Watch the 60-second FreshSense product and AI workflow demo](docs/demo/freshsense-recruiter-demo-60s.mp4)

The video follows one inspection from batch upload through computer vision,
Agent follow-up, human review, Manager Chat, and the daily quality report.
```

- [ ] **Step 7: Run repository-level regression checks**

From the repository root run:

```powershell
py -3.11 -m pytest -q
npm.cmd --prefix web test -- --run
npm.cmd --prefix web run build
npm.cmd --prefix video test
npm.cmd --prefix video run typecheck
npm.cmd --prefix video run verify
git diff --check
```

Expected: Python tests, web tests, web build, video tests, type checking, media verification, and diff check all pass.

- [ ] **Step 8: Commit the verified public demo**

Force-add only the accepted generated media files because audio and captions are ignored during iteration:

```powershell
git add video/scripts/verify-output.ts video/tests/output-validation.test.ts README.md docs/demo/freshsense-recruiter-demo-60s.mp4
git add -f video/public/audio/narration.wav video/public/audio/ambient.wav video/public/captions/narration.json
git commit -m "Publish FreshSense recruiter demo video"
```

- [ ] **Step 9: Review the final branch diff**

Run:

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
git diff --check origin/main...HEAD
```

Expected: only the approved design document, implementation plan, `video/` source and assets, final MP4, `.gitignore`, and README link differ from `origin/main`; the worktree has no tracked uncommitted changes.
