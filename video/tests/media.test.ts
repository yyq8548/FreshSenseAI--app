import type {Caption} from '@remotion/captions';
import {
  existsSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {describe, expect, it} from 'vitest';
import {NARRATION_TEXT} from '../src/content';
import {
  getAmbientFfmpegArgs,
  getRemotionInvocation,
  groupWhisperCaptionsIntoWords,
  mergeZeroDurationCaptions,
  retimeCaptionsToNarration,
  validateCaptions,
  validateNarrationDuration,
  withCleanOutput,
} from '../src/media';

const caption = (text: string, startMs: number, endMs: number): Caption => ({
  text,
  startMs,
  endMs,
  timestampMs: null,
  confidence: 1,
});

const joinedCaptionText = (captions: readonly Caption[]) =>
  captions
    .map(({text}) => text)
    .join('')
    .replace(/\s+/g, ' ')
    .trim();

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

  it('groups unequal split Whisper tokens and reconstructs the exact narration', () => {
    const rawTokens: Caption[] = [];
    let cursor = 100;
    for (const word of NARRATION_TEXT.split(/\s+/)) {
      const fragments =
        word === 'FreshSense'
          ? [' Fresh', 'Sense']
          : word === 'DenseNet201'
            ? [' Dense', 'Net', '201']
            : [` ${word}`];
      for (const fragment of fragments) {
        rawTokens.push(caption(fragment, cursor, cursor + 100));
        cursor += 100;
      }
    }
    expect(rawTokens).toHaveLength(116);
    const spokenWords = groupWhisperCaptionsIntoWords(rawTokens);
    expect(spokenWords).toHaveLength(112);
    const alignment = retimeCaptionsToNarration(rawTokens, NARRATION_TEXT);
    expect(joinedCaptionText(alignment.captions)).toBe(NARRATION_TEXT);
    expect(validateCaptions(alignment.captions)).toEqual([]);
    expect(alignment.coverage).toBe(1);
    expect(alignment.score).toBe(1);
  });

  it('maps mistranscribed brands as local substitutions', () => {
    const rawTokens = [
      caption(' Freshes', 100, 250),
      caption(' links', 250, 400),
      caption(' FreshesENSCAI', 400, 550),
      caption('.com', 550, 650),
    ];
    const alignment = retimeCaptionsToNarration(
      rawTokens,
      'FreshSense links freshsenseai.com',
    );
    expect(joinedCaptionText(alignment.captions)).toBe(
      'FreshSense links freshsenseai.com',
    );
    expect(alignment.captions[0]).toMatchObject({
      text: 'FreshSense',
      startMs: 100,
      endMs: 250,
    });
    expect(alignment.captions[2]).toMatchObject({
      text: ' freshsenseai.com',
      startMs: 400,
      endMs: 650,
    });
  });

  it('keeps later words locally aligned across recognized insertion and deletion', () => {
    const withInsertion = retimeCaptionsToNarration(
      [
        caption(' Staff', 0, 100),
        caption(' really', 100, 250),
        caption(' confirm', 250, 400),
        caption(' results.', 400, 600),
      ],
      'Staff confirm results.',
    );
    expect(withInsertion.captions[1]).toMatchObject({
      text: ' confirm',
      startMs: 250,
      endMs: 400,
    });
    expect(withInsertion.captions[2]).toMatchObject({
      text: ' results.',
      startMs: 400,
      endMs: 600,
    });

    const withDeletion = retimeCaptionsToNarration(
      [
        caption(' Staff', 0, 100),
        caption(' confirm', 300, 450),
        caption(' results.', 450, 600),
      ],
      'Staff carefully confirm results.',
    );
    expect(withDeletion.captions[1]).toMatchObject({
      text: ' carefully',
      startMs: 100,
      endMs: 300,
    });
    expect(withDeletion.captions[2]).toMatchObject({
      text: ' confirm',
      startMs: 300,
      endMs: 450,
    });
    expect(validateCaptions(withDeletion.captions)).toEqual([]);
  });

  it('rejects unrelated low-quality transcript alignment', () => {
    expect(() =>
      retimeCaptionsToNarration(
        [
          caption(' weather', 0, 100),
          caption(' clouds', 100, 200),
          caption(' dancing', 200, 300),
        ],
        'FreshSense checks fruit',
      ),
    ).toThrow(/Caption alignment is too low quality/);
  });
});

describe('caption output cleanup', () => {
  it('removes stale and partial caption output when generation fails', async () => {
    const root = mkdtempSync(join(tmpdir(), 'freshsense-captions-'));
    const output = join(root, 'narration.json');
    try {
      writeFileSync(output, 'stale', 'utf8');
      await expect(
        withCleanOutput(output, async () => {
          expect(existsSync(output)).toBe(false);
          writeFileSync(output, 'partial', 'utf8');
          throw new Error('transcription failed');
        }),
      ).rejects.toThrow('transcription failed');
      expect(existsSync(output)).toBe(false);
    } finally {
      rmSync(root, {recursive: true, force: true});
    }
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
