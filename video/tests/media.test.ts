import type {Caption} from '@remotion/captions';
import {describe, expect, it} from 'vitest';
import {NARRATION_TEXT} from '../src/content';
import {
  getAmbientFfmpegArgs,
  getRemotionInvocation,
  mergeZeroDurationCaptions,
  retimeCaptionsToNarration,
  validateCaptions,
  validateNarrationDuration,
} from '../src/media';

const caption = (text: string, startMs: number, endMs: number): Caption => ({
  text,
  startMs,
  endMs,
  timestampMs: null,
  confidence: 1,
});

describe('caption validation', () => {
  it('accepts ordered non-overlapping captions inside 60 seconds', () => {
    expect(
      validateCaptions([
        caption(' Fruit checks happen fast.', 200, 1800),
        caption(' FreshSense records the work.', 1900, 3500),
      ]),
    ).toEqual([]);
  });

  it('rejects overlap and captions beyond the composition', () => {
    expect(
      validateCaptions([
        caption(' one', 0, 2000),
        caption(' two', 1900, 61000),
      ]),
    ).toEqual([
      'caption 1 overlaps caption 0',
      'caption 1 ends after the composition',
    ]);
  });

  it('merges zero-duration Whisper fragments without losing transcript text', () => {
    expect(
      mergeZeroDurationCaptions([
        caption(' Man', 100, 400),
        caption('agers', 400, 400),
        caption(' ask', 400, 800),
        caption('.', 800, 800),
      ]),
    ).toEqual([
      caption(' Managers', 100, 400),
      caption(' ask.', 400, 800),
    ]);
  });

  it('keeps an all-zero transcript invalid instead of dropping its text', () => {
    const merged = mergeZeroDurationCaptions([
      caption(' all', 100, 100),
      caption(' zero', 100, 100),
    ]);
    expect(merged).toEqual([caption(' all zero', 100, 100)]);
    expect(validateCaptions(merged)).toEqual(['caption 0 has no duration']);
  });

  it('merges a leading zero-duration fragment into the first timed caption', () => {
    expect(
      mergeZeroDurationCaptions([
        caption(' Fresh', 100, 100),
        caption('Sense', 100, 500),
      ]),
    ).toEqual([caption(' FreshSense', 100, 500)]);
  });

  it('merges a trailing zero-duration fragment into the last timed caption', () => {
    expect(
      mergeZeroDurationCaptions([
        caption(' freshsenseai', 100, 500),
        caption('.com', 500, 500),
      ]),
    ).toEqual([caption(' freshsenseai.com', 100, 500)]);
  });

  it('preserves negative-duration captions for validation failure', () => {
    const merged = mergeZeroDurationCaptions([
      caption(' backwards', 500, 400),
    ]);
    expect(merged).toEqual([caption(' backwards', 500, 400)]);
    expect(validateCaptions(merged)).toEqual(['caption 0 has no duration']);
  });

  it('rejects empty caption output', () => {
    expect(validateCaptions([])).toEqual(['captions are empty']);
  });

  it('retimes the exact approved narration from Whisper timing boundaries', () => {
    const whisperTiming = NARRATION_TEXT.split(/\s+/).map((_, index) =>
      caption(` wrong${index}`, index * 100, (index + 1) * 100),
    );
    const rebuilt = retimeCaptionsToNarration(
      whisperTiming,
      NARRATION_TEXT,
    );
    const reconstructed = rebuilt
      .map(({text}) => text)
      .join('')
      .replace(/\s+/g, ' ')
      .trim();
    expect(reconstructed).toBe(NARRATION_TEXT);
    expect(reconstructed).toContain('FreshSense');
    expect(reconstructed).toContain('DenseNet201');
    expect(reconstructed).toContain('FastAPI');
    expect(reconstructed).toContain('PostgreSQL');
    expect(reconstructed).toContain('Azure');
    expect(reconstructed).toContain('freshsenseai.com');
    expect(rebuilt[0].startMs).toBe(whisperTiming[0].startMs);
    expect(rebuilt.at(-1)?.endMs).toBe(whisperTiming.at(-1)?.endMs);
  });
});

describe('narration duration validation', () => {
  it('accepts the calibrated narration duration', () => {
    expect(validateNarrationDuration(59.404626)).toEqual([]);
  });

  it('rejects narration at or beyond 59.5 seconds', () => {
    expect(validateNarrationDuration(59.5)).toEqual([
      'narration must be shorter than 59.5 seconds (received 59.5)',
    ]);
    expect(validateNarrationDuration(60)).toEqual([
      'narration must be shorter than 59.5 seconds (received 60)',
    ]);
  });
});

describe('Remotion media commands', () => {
  it('invokes the local Remotion CLI through Node without a command shell', () => {
    expect(getRemotionInvocation('C:\\video', 'C:\\node.exe')).toEqual({
      command: 'C:\\node.exe',
      prefixArgs: [
        'C:\\video\\node_modules\\@remotion\\cli\\remotion-cli.js',
      ],
    });
  });

  it('builds the ambient bed from filters bundled with Remotion FFmpeg', () => {
    const args = getAmbientFfmpegArgs('ambient.wav');
    expect(args).toEqual([
      '-f',
      'lavfi',
      '-i',
      'sine=frequency=110:sample_rate=48000:duration=60',
      '-f',
      'lavfi',
      '-i',
      'sine=frequency=164.81:sample_rate=48000:duration=60',
      '-f',
      'lavfi',
      '-i',
      'sine=frequency=220:sample_rate=48000:duration=60',
      '-filter_complex',
      "[0:a]volume=0.128[a0];[1:a]volume=0.080[a1];[2:a]volume=0.064[a2];[a0][a1][a2]amix=inputs=3:normalize=0,volume='if(lt(t\\,2)\\,t/2\\,if(gt(t\\,57)\\,(60-t)/3\\,1))':eval=frame[out]",
      '-map',
      '[out]',
      '-c:a',
      'pcm_s16le',
      'ambient.wav',
      '-y',
    ]);
  });
});
