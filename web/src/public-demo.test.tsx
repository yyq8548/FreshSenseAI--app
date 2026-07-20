import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { enableVideoSound, PublicDemoPage } from "./PublicDemoPage";

describe("PublicDemoPage", () => {
  it("renders the public muted-autoplay player and fallback actions", () => {
    const html = renderToStaticMarkup(<PublicDemoPage />);
    const normalizedHtml = html.toLowerCase();
    expect(html).toContain("FreshSense in 60 seconds");
    expect(normalizedHtml).toContain("autoplay");
    expect(normalizedHtml).toContain("muted");
    expect(normalizedHtml).toContain("playsinline");
    expect(html).toContain('preload="metadata"');
    expect(html).toContain("/demo/freshsense-recruiter-demo-60s.mp4");
    expect(html).toContain("/demo/freshsense-demo-thumbnail.png");
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
