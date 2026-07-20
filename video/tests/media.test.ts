import type {Caption} from '@remotion/captions';
import {describe, expect, it} from 'vitest';
import {
  getAmbientFfmpegArgs,
  getRemotionInvocation,
  mergeZeroDurationCaptions,
  validateCaptions,
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
    expect(args.filter((arg) => arg === '-i')).toHaveLength(3);
    expect(args.join(' ')).toContain('sine=frequency=110');
    expect(args.join(' ')).toContain('amix=inputs=3:normalize=0');
    expect(args.join(' ')).not.toContain('aevalsrc');
    expect(args.slice(-4)).toEqual(['-c:a', 'pcm_s16le', 'ambient.wav', '-y']);
  });
});
