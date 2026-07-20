import type {Caption} from '@remotion/captions';
import {join} from 'node:path';

export const getRemotionInvocation = (
  videoRoot: string,
  nodeExecutable = process.execPath,
): {command: string; prefixArgs: string[]} => ({
  command: nodeExecutable,
  prefixArgs: [
    join(
      videoRoot,
      'node_modules',
      '@remotion',
      'cli',
      'remotion-cli.js',
    ),
  ],
});

export const getAmbientFfmpegArgs = (output: string): string[] => [
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
  output,
  '-y',
];

export const mergeZeroDurationCaptions = (
  captions: readonly Caption[],
): Caption[] => {
  const merged: Caption[] = [];
  let leadingCaption: Caption | null = null;
  for (const caption of captions) {
    if (caption.endMs === caption.startMs) {
      if (merged.length === 0) {
        if (leadingCaption === null) {
          leadingCaption = {...caption};
        } else {
          leadingCaption.text += caption.text;
        }
      } else {
        const previous = merged[merged.length - 1];
        merged[merged.length - 1] = {
          ...previous,
          text: previous.text + caption.text,
        };
      }
      continue;
    }
    merged.push({
      ...caption,
      text: (leadingCaption?.text ?? '') + caption.text,
    });
    leadingCaption = null;
  }
  if (leadingCaption) {
    merged.push(leadingCaption);
  }
  return merged;
};

export const retimeCaptionsToNarration = (
  timingCaptions: readonly Caption[],
  narration: string,
): Caption[] => {
  const words = narration.trim().split(/\s+/).filter(Boolean);
  if (timingCaptions.length === 0 || words.length === 0) {
    return [];
  }
  if (timingCaptions.length < words.length) {
    throw new Error(
      `Not enough Whisper timing captions: ${timingCaptions.length} for ${words.length} narration words.`,
    );
  }
  return words.map((word, index) => {
    const startIndex = Math.floor(
      (index * timingCaptions.length) / words.length,
    );
    const nextIndex = Math.floor(
      ((index + 1) * timingCaptions.length) / words.length,
    );
    const source = timingCaptions[startIndex];
    return {
      ...source,
      text: `${index === 0 ? '' : ' '}${word}`,
      endMs:
        index === words.length - 1
          ? timingCaptions[timingCaptions.length - 1].endMs
          : timingCaptions[nextIndex].startMs,
    };
  });
};

export const validateNarrationDuration = (durationSeconds: number): string[] =>
  Number.isFinite(durationSeconds) &&
  durationSeconds > 0 &&
  durationSeconds < 59.5
    ? []
    : [
        `narration must be shorter than 59.5 seconds (received ${durationSeconds})`,
      ];

export const validateCaptions = (captions: readonly Caption[]): string[] => {
  const errors: string[] = [];
  if (captions.length === 0) {
    errors.push('captions are empty');
  }
  captions.forEach((caption, index) => {
    if (caption.endMs <= caption.startMs) {
      errors.push(`caption ${index} has no duration`);
    }
    if (index > 0 && caption.startMs < captions[index - 1].endMs) {
      errors.push(`caption ${index} overlaps caption ${index - 1}`);
    }
    if (caption.endMs > 60000) {
      errors.push(`caption ${index} ends after the composition`);
    }
  });
  return errors;
};
