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
          <span className="demo-brand-mark" aria-hidden="true">
            FS
          </span>
          <span>
            <strong>FreshSense</strong>
            <small>Public product demo</small>
          </span>
        </a>
        <a className="demo-header-link" href={githubRepository}>
          GitHub repository
        </a>
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
            <span role="status" aria-live="polite">
              {playbackMessage}
            </span>
          </div>
        </section>

        <nav className="demo-actions" aria-label="Demo links">
          <a className="demo-primary-action" href="/">
            Open FreshSense
          </a>
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
