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
  let leadingText = '';
  for (const caption of captions) {
    if (caption.endMs <= caption.startMs) {
      if (merged.length === 0) {
        leadingText += caption.text;
      } else {
        const previous = merged[merged.length - 1];
        merged[merged.length - 1] = {
          ...previous,
          text: previous.text + caption.text,
        };
      }
      continue;
    }
    merged.push({...caption, text: leadingText + caption.text});
    leadingText = '';
  }
  return merged;
};

export const validateCaptions = (captions: readonly Caption[]): string[] => {
  const errors: string[] = [];
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
