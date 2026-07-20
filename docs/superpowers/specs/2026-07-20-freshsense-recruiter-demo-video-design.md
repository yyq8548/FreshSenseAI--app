# FreshSense recruiter demo video design

Date: 2026-07-20

Status: Approved concept, ready for implementation planning

Audience: Recruiting managers and AI Engineer interviewers

Primary use: GitHub project page and quick portfolio review

## Goal

Create a 60-second English product documentary that shows FreshSense as a working AI inspection system for small grocery teams. The video should make the product workflow clear without requiring the viewer to read the repository first.

The story starts with the store workflow, then reveals the computer vision, bounded Agent, human review, and manager tools that support it. The video must use the real FreshSense interface. It must not imply that the model makes food-safety decisions or that unfinished features are available.

## Deliverable

- One 1920 by 1080 MP4 at 30 frames per second
- Target duration: 60 seconds, with a tolerance of 2 seconds
- H.264 video with English narration, English captions, and a light music bed
- Output path: `docs/demo/freshsense-recruiter-demo-60s.mp4`
- README link updated to the new video
- Source project stored under `video/`

## Creative direction

### Format

Product documentary. The edit should feel like a concise walkthrough of a real operating tool, not an advertisement or a feature montage.

### Visual language

- Warm white background, FreshSense green accents, and charcoal text
- Real product screenshots only
- Slow, deliberate camera moves across screenshots
- Fine-line callouts for the few controls that need explanation
- Short fades and simple cuts
- No mock dashboards, stock footage, fake metrics, or decorative AI imagery
- Clean title and closing cards

### Audio

- Calm, natural, neutral English voice
- Clear delivery at roughly 135 to 150 words per minute
- English captions throughout the narration
- Low-volume original ambient music with no lyrics
- Narration stays dominant in the mix
- The edit remains understandable when muted

## Story and timing

The final narration may be tightened after the voice test, but it must preserve these claims and safety boundaries.

| Time | Story beat | Picture | Narration direction | On-screen text |
| --- | --- | --- | --- | --- |
| 0:00 to 0:05 | The problem | Minimal title card, then a quick crop of the inspection overview | Fruit checks happen fast, but the record often disappears with the shift. | `FreshSense` and `AI-assisted fruit inspection for small grocery teams` |
| 0:05 to 0:12 | Product overview | `overview.png`, moving from summary cards to recent activity | FreshSense gives small grocery teams one place to inspect fruit and follow review work. | `One shared inspection workspace` |
| 0:12 to 0:23 | Batch inspection | `batch-inspection.png`, first showing the image picker, then the result column | Staff can take a photo or add twenty images at once. The model covers six named fruit types. Photos are not stored by default. | `Camera or multi-photo upload`, `Up to 20 images`, `Photos not stored by default` |
| 0:23 to 0:33 | Vision and safe rejection | Continue on `batch-inspection.png`, with restrained labels pointing to the result and processing state | DenseNet201 looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs instead of forcing a label. | `DenseNet201 classifier`, `Supported-input gate`, `Uncertain results are withheld` |
| 0:33 to 0:43 | Bounded Agent workflow | `agent-activity.png`, moving from open tasks to notifications and approvals | A bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval. | `History and reviewed knowledge`, `Automatic follow-up tasks`, `Human approval for high-risk actions` |
| 0:43 to 0:50 | Human review | `review-queue.png`, centered on the observed outcome control and save action | Staff confirm or correct results in the review queue. | `Human review stays in control` |
| 0:50 to 0:56 | Manager tools | Fast cut from `manager-chat.png` to `daily-report.png` | Managers ask grounded questions about inspection history and Agent decisions, then check the daily report. | `Grounded Manager Chat`, `Daily quality report` |
| 0:56 to 1:00 | Stack and call to action | Closing card with product URL, repository, and a compact stack line | FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try the live beta or review the code on GitHub. | `freshsenseai.com`, `github.com/yyq8548/FreshSenseAI--app` |

## Working voiceover

This 138-word script is the timing baseline:

> Fruit checks happen fast, but the record often disappears with the shift. FreshSense gives small grocery teams one place to inspect fruit and follow review work. Staff can take a photo or add twenty images at once. The model covers apples, bananas, oranges, mangoes, tomatoes, and pears. Photos are not stored by default. A DenseNet201 classifier looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs instead of forcing a label. Next, a bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval. Staff confirm or correct results in the review queue. Managers ask grounded questions about inspection history and Agent decisions, then check the daily report. FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try freshsenseai.com, or view the code on GitHub.

## Narration constraints

The script should sound like an engineer explaining a product they built. Use concrete verbs and short sentences. Avoid claims such as production-ready, enterprise-grade, autonomous food-safety decision-making, or independently validated accuracy.

The finished script must state or make clear that:

- FreshSense evaluates visible patterns only.
- The current classifier supports six named fruit types.
- The supported-input gate can return an uncertain or unsupported result.
- Staff review the output.
- High-risk Agent actions require manager approval.
- Uploaded photos are not retained by default.

## Screenshot assets

Use the existing product captures as source material:

- `docs/images/workbench/overview.png`
- `docs/images/workbench/batch-inspection.png`
- `docs/images/workbench/review-queue.png`
- `docs/images/workbench/agent-activity.png`
- `docs/images/workbench/manager-chat.png`
- `docs/images/workbench/daily-report.png`
- `docs/images/workbench/team.png`

The first six screenshots appear in the core edit. `team.png` is available as a substitute or brief supporting shot if pacing allows. Do not alter values shown in a screenshot.

## Remotion project structure

The video source should remain separate from the product application:

```text
video/
|-- package.json
|-- remotion.config.ts
|-- src/
|   |-- index.ts
|   |-- Root.tsx
|   |-- FreshSenseDemo.tsx
|   |-- scenes.ts
|   `-- components/
|       |-- TitleCard.tsx
|       |-- ScreenshotScene.tsx
|       |-- Callout.tsx
|       |-- CaptionTrack.tsx
|       |-- TechStack.tsx
|       `-- ClosingCard.tsx
`-- public/
    |-- screens/
    `-- audio/
```

`scenes.ts` is the source of truth for scene boundaries, narration, captions, screenshot selection, and callouts. Components should calculate motion from the current frame and Remotion timing utilities. Avoid browser CSS transitions because they do not provide deterministic frame output.

## Motion and layout

- Keep important product content inside a 10 percent title-safe margin.
- Use screenshot crops that preserve labels and controls at readable sizes.
- Limit each scene to one main camera move.
- Callouts should appear only after the viewer has seen the relevant area.
- Use subtle easing for pans, zooms, and opacity changes.
- Captions should use no more than two lines at a time.
- Keep captions clear of the product controls being discussed.
- Provide sufficient text contrast on every frame.

## Voice, captions, and music

Narration is a required asset. If a natural voice track cannot be produced, the build must stop instead of publishing a silent placeholder.

Captions must be timed from the final voice track, not estimated from the draft. Music should be original or carry a license that permits redistribution in a public GitHub repository. Store its attribution or license beside the audio asset when required.

## Failure handling

The render should fail early when:

- a referenced screenshot is missing;
- the final narration file is missing;
- a caption starts before the previous caption ends;
- scene durations do not cover the full composition;
- the output duration falls outside the accepted range; or
- the rendered file has no audio stream.

Do not silently replace missing product assets with placeholders.

## Verification

Before the final render:

1. Validate every asset path and every scene boundary.
2. Render still frames near 0, 15, 30, 45, and 59 seconds.
3. Inspect those frames for crop quality, legibility, accurate callouts, and caption placement.
4. Preview the narration and caption timing together.
5. Render the complete MP4.
6. Verify 1920 by 1080 resolution, 30 frames per second, H.264 video, an audio stream, and a duration between 58 and 62 seconds.
7. Watch the complete file once with audio and once muted.
8. Confirm that every product claim matches the repository and current hosted beta.

## Acceptance criteria

The video is complete when a recruiter can understand these points in one viewing:

- FreshSense is a working inspection workspace, not only a classifier notebook.
- Staff can submit several photos in one batch.
- The computer vision model can abstain instead of forcing a label.
- A bounded Agent creates follow-up work from inspection context.
- Humans review visible-condition results and approve high-risk actions.
- Managers can inspect history, ask grounded questions, and read a daily report.
- The product has a live beta and a public code repository.

## Out of scope

- Changes to the FreshSense web application or model
- Website redeployment
- New product screenshots or fabricated customer data
- Claims about arbitrary-object detection or independent real-world accuracy
- Paid advertising cuts, vertical social formats, or translated versions
- Automatic publication to GitHub Releases
