# FreshSense public demo page design

**Date:** 2026-07-20  
**Status:** Approved
**Audience:** Recruiters, AI Engineer interviewers, prospective pilot users

## Goal

Make the FreshSense demo immediately understandable from GitHub without asking a
visitor to sign in or download the repository. The README will show a real
16:9 video thumbnail. Selecting it opens a public player at
`https://freshsenseai.com/demo`.

## Success criteria

- `/demo` is public and does not initialize Microsoft Entra authentication.
- The page begins muted playback automatically when the browser permits it.
- The viewer can enable sound with an explicit, accessible control and can also
  use native video controls.
- The player uses the accepted 60-second recruiter demo and a matching poster.
- The README thumbnail links to `/demo` and appears before Product overview.
- The README keeps a direct GitHub MP4 fallback plus checksum and manifest links.
- The production build contains one deployed copy of the canonical MP4 without
  committing a second source copy to Git.
- Existing authenticated FreshSense routes and behavior remain unchanged.

## Approaches considered

### Existing React application with a public route — selected

Add a lightweight public entry path to the deployed React application. It keeps
FreshSense branding, uses the existing Azure Static Web Apps deployment, and
does not add a third-party video provider.

### Standalone static HTML page

This would isolate the demo, but duplicate layout, styling, metadata, and build
logic that already belong to the React application.

### YouTube or Vimeo embed

This offers mature streaming, but introduces external branding, tracking,
availability, and account dependencies. It is unnecessary for the expected
portfolio traffic.

## Architecture

The application bootstrap checks the normalized browser pathname before loading
runtime configuration or creating the MSAL client.

- `/demo` and `/demo/` render `PublicDemoPage` directly.
- All other paths continue through the existing configuration and Entra-authenticated
  application bootstrap.
- The demo page does not call the FreshSense API and does not require environment
  variables, tokens, cookies, or workspace data.
- Azure Static Web Apps continues using its navigation fallback so a direct visit
  to `/demo` resolves to the SPA entry document.

Route recognition will be implemented as a small pure function so public-path
behavior can be tested independently from the browser and authentication SDK.

## Media delivery

The canonical accepted video remains:

`docs/demo/freshsense-recruiter-demo-60s.mp4`

A prebuild script copies the video, checksum, manifest, and poster into a
generated directory under `web/public/demo/`. Vite then includes those files in
`web/dist/demo/`. Generated copies are ignored by Git; only the canonical source
artifact, poster, and synchronization code are committed.

The synchronization step fails when a required source is missing, empty, or
does not match the published checksum. This prevents a deployment containing a
broken or stale player.

## Page experience

The public page uses a compact FreshSense header, one clear headline, a short
workflow description, and a centered 16:9 player.

Player behavior:

- `autoPlay`, `muted`, and `playsInline` are enabled initially;
- native controls remain visible;
- preload is limited to metadata;
- the generated poster is visible before playback begins;
- an `Enable sound` button unmutes the current video and requests playback;
- if autoplay is blocked, the poster and native play control remain usable;
- motion respects the user's reduced-motion preference by avoiding decorative
  animation.

Below the player, three actions are available:

- **Open FreshSense** — returns to the hosted application;
- **View source on GitHub** — opens the repository;
- **Download MP4** — opens the canonical GitHub-hosted video as a fallback.

The page also repeats the visual-decision-support limitation in concise language
so the demo does not imply food-safety certification.

## README thumbnail

The thumbnail is a 16:9 PNG derived from an actual frame of the accepted video.
It preserves the real interface and adds only a centered circular play symbol
and subtle contrast treatment. The image is committed under
`docs/images/workbench/` and links to `https://freshsenseai.com/demo`.

The current text-only demo link is replaced by the linked thumbnail. A short
fallback line retains direct links to the MP4, checksum, and media manifest.

## Accessibility and privacy

- The thumbnail has descriptive alternative text.
- Player and sound controls have accessible names and visible focus states.
- Text and controls meet practical contrast requirements.
- Playback starts muted; enabling sound always requires user interaction.
- The page collects no form data and adds no analytics, advertising, or
  third-party embeds.
- Captions are already burned into the accepted video; the page does not claim a
  separate selectable caption track.

## Error handling

- A missing deployment asset fails the build instead of producing a dead page.
- A browser playback error leaves the poster, native controls, and download link
  available.
- Failure to unmute or resume playback does not hide the native controls.
- The page never redirects a demo visitor into the login flow.

## Testing

Tests will cover:

- exact matching for `/demo` and `/demo/`, and rejection of unrelated paths;
- public bootstrap selection before configuration and MSAL initialization;
- required video attributes, public links, safety copy, and accessible control;
- media synchronization, checksum validation, and missing-file failure;
- existing web tests and production build;
- a local browser visit to `/demo`, including muted autoplay state, sound toggle,
  poster, fallback links, responsive layout, and no authentication redirect;
- the deployed `https://freshsenseai.com/demo` route after Azure publication.

## Deployment and rollback

The feature uses the existing Azure Static Web Apps workflow and custom domain.
No new Azure resource is required. The deployed route is validated before the
README change is published so the thumbnail never points to a missing page.

Rollback consists of reverting the demo-page commit and redeploying the previous
Static Web Apps build. The canonical GitHub MP4 and its verification files remain
available independently.

## Out of scope

- YouTube, Vimeo, or another hosted video account;
- analytics or view tracking;
- automatic playback with sound;
- editing the accepted video content;
- changes to the authenticated workbench, API, model, Agent, or database.
