import type {Caption} from '@remotion/captions';
import {rmSync} from 'node:fs';
import {join, posix, win32} from 'node:path';

export const DEFAULT_EDGE_TTS_VOICE = 'en-US-AvaNeural';

export const getSystemPythonExecutable = (
  platform: NodeJS.Platform = process.platform,
): string => (platform === 'win32' ? 'python' : 'python3');

export const getVoicePythonExecutable = (
  tempRoot: string,
  platform: NodeJS.Platform = process.platform,
): string =>
  platform === 'win32'
    ? win32.join(tempRoot, 'edge-tts-venv', 'Scripts', 'python.exe')
    : posix.join(tempRoot, 'edge-tts-venv', 'bin', 'python');

export const getEdgeTtsInvocation = (
  pythonExecutable: string,
  textPath: string,
  outputPath: string,
  voice = DEFAULT_EDGE_TTS_VOICE,
): {command: string; args: string[]} => ({
  command: pythonExecutable,
  args: [
    '-m',
    'edge_tts',
    '--voice',
    voice,
    '--file',
    textPath,
    '--write-media',
    outputPath,
  ],
});

export const getNarrationFfmpegArgs = (
  inputPath: string,
  outputPath: string,
): string[] => [
  '-i',
  inputPath,
  '-ar',
  '48000',
  '-ac',
  '1',
  '-c:a',
  'pcm_s16le',
  outputPath,
  '-y',
];

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

export const groupWhisperCaptionsIntoWords = (
  captions: readonly Caption[],
): Caption[] => {
  const words: Caption[] = [];
  for (const caption of captions) {
    const text = caption.text.trim();
    if (text.length === 0) {
      continue;
    }
    if (words.length === 0 || /^\s/.test(caption.text)) {
      words.push({...caption, text});
      continue;
    }
    const previous = words[words.length - 1];
    words[words.length - 1] = {
      ...previous,
      text: previous.text + text,
      endMs: caption.endMs,
      confidence:
        previous.confidence === null
          ? caption.confidence
          : caption.confidence === null
            ? previous.confidence
            : Math.min(previous.confidence, caption.confidence),
    };
  }
  return words;
};

const normalizeAlignmentWord = (word: string) =>
  word.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]/g, '');

const levenshteinDistance = (left: string, right: string): number => {
  const row = Array.from({length: right.length + 1}, (_, index) => index);
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex++) {
    let diagonal = row[0];
    row[0] = leftIndex;
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex++) {
      const above = row[rightIndex];
      row[rightIndex] = Math.min(
        row[rightIndex] + 1,
        row[rightIndex - 1] + 1,
        diagonal +
          (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1),
      );
      diagonal = above;
    }
  }
  return row[right.length];
};

const wordSimilarity = (left: string, right: string): number => {
  const normalizedLeft = normalizeAlignmentWord(left);
  const normalizedRight = normalizeAlignmentWord(right);
  const longest = Math.max(normalizedLeft.length, normalizedRight.length);
  return longest === 0
    ? 1
    : 1 - levenshteinDistance(normalizedLeft, normalizedRight) / longest;
};

export type CaptionAlignment = {
  captions: Caption[];
  score: number;
  coverage: number;
  recognizedWordCount: number;
};

export const retimeCaptionsToNarration = (
  timingCaptions: readonly Caption[],
  narration: string,
): CaptionAlignment => {
  const recognizedWords = groupWhisperCaptionsIntoWords(timingCaptions);
  const words = narration.trim().split(/\s+/).filter(Boolean);
  if (recognizedWords.length === 0 || words.length === 0) {
    throw new Error('Caption alignment requires recognized and approved words.');
  }
  const gapCost = 0.75;
  const costs = Array.from({length: words.length + 1}, () =>
    Array(recognizedWords.length + 1).fill(0),
  );
  const steps = Array.from({length: words.length + 1}, () =>
    Array<'pair' | 'approved-gap' | 'recognized-gap' | null>(
      recognizedWords.length + 1,
    ).fill(null),
  );
  for (let approvedIndex = 1; approvedIndex <= words.length; approvedIndex++) {
    costs[approvedIndex][0] = approvedIndex * gapCost;
    steps[approvedIndex][0] = 'approved-gap';
  }
  for (
    let recognizedIndex = 1;
    recognizedIndex <= recognizedWords.length;
    recognizedIndex++
  ) {
    costs[0][recognizedIndex] = recognizedIndex * gapCost;
    steps[0][recognizedIndex] = 'recognized-gap';
  }
  for (let approvedIndex = 1; approvedIndex <= words.length; approvedIndex++) {
    for (
      let recognizedIndex = 1;
      recognizedIndex <= recognizedWords.length;
      recognizedIndex++
    ) {
      const pair =
        costs[approvedIndex - 1][recognizedIndex - 1] +
        1 -
        wordSimilarity(
          words[approvedIndex - 1],
          recognizedWords[recognizedIndex - 1].text,
        );
      const approvedGap =
        costs[approvedIndex - 1][recognizedIndex] + gapCost;
      const recognizedGap =
        costs[approvedIndex][recognizedIndex - 1] + gapCost;
      if (pair <= approvedGap && pair <= recognizedGap) {
        costs[approvedIndex][recognizedIndex] = pair;
        steps[approvedIndex][recognizedIndex] = 'pair';
      } else if (approvedGap <= recognizedGap) {
        costs[approvedIndex][recognizedIndex] = approvedGap;
        steps[approvedIndex][recognizedIndex] = 'approved-gap';
      } else {
        costs[approvedIndex][recognizedIndex] = recognizedGap;
        steps[approvedIndex][recognizedIndex] = 'recognized-gap';
      }
    }
  }

  const recognizedByApproved: Array<number | null> = Array(words.length).fill(
    null,
  );
  let approvedIndex = words.length;
  let recognizedIndex = recognizedWords.length;
  while (approvedIndex > 0 || recognizedIndex > 0) {
    const step = steps[approvedIndex][recognizedIndex];
    if (step === 'pair') {
      recognizedByApproved[approvedIndex - 1] = recognizedIndex - 1;
      approvedIndex--;
      recognizedIndex--;
    } else if (step === 'approved-gap') {
      approvedIndex--;
    } else if (step === 'recognized-gap') {
      recognizedIndex--;
    } else {
      throw new Error('Caption alignment backtrace failed.');
    }
  }

  const alignedCount = recognizedByApproved.filter(
    (index) => index !== null,
  ).length;
  const coverage = alignedCount / words.length;
  const score = Math.max(
    0,
    1 -
      costs[words.length][recognizedWords.length] /
        Math.max(words.length, recognizedWords.length),
  );
  if (score < 0.55 || coverage < 0.7) {
    throw new Error(
      `Caption alignment is too low quality (score ${score.toFixed(3)}, coverage ${coverage.toFixed(3)}).`,
    );
  }

  const captions: Array<Caption | null> = words.map((word, index) => {
    const sourceIndex = recognizedByApproved[index];
    return sourceIndex === null
      ? null
      : {
          ...recognizedWords[sourceIndex],
          text: `${index === 0 ? '' : ' '}${word}`,
        };
  });
  let index = 0;
  while (index < captions.length) {
    if (captions[index] !== null) {
      index++;
      continue;
    }
    const runStart = index;
    while (index < captions.length && captions[index] === null) {
      index++;
    }
    const previous = captions[runStart - 1];
    const next = captions[index];
    if (!previous || !next || next.startMs <= previous.endMs) {
      throw new Error(
        `Cannot locally interpolate approved words ${runStart}-${index - 1}.`,
      );
    }
    const segmentDuration =
      (next.startMs - previous.endMs) / (index - runStart);
    for (let missingIndex = runStart; missingIndex < index; missingIndex++) {
      captions[missingIndex] = {
        text: ` ${words[missingIndex]}`,
        startMs:
          previous.endMs + segmentDuration * (missingIndex - runStart),
        endMs:
          previous.endMs + segmentDuration * (missingIndex - runStart + 1),
        timestampMs: null,
        confidence: null,
      };
    }
  }
  return {
    captions: captions as Caption[],
    score,
    coverage,
    recognizedWordCount: recognizedWords.length,
  };
};

export const withCleanOutput = async <Result>(
  outputPath: string,
  generate: () => Promise<Result>,
): Promise<Result> => {
  rmSync(outputPath, {force: true});
  try {
    return await generate();
  } catch (error) {
    rmSync(outputPath, {force: true});
    throw error;
  }
};

export const withCleanOutputsSync = <Result>(
  outputPaths: readonly string[],
  generate: () => Result,
): Result => {
  const clean = () => {
    for (const outputPath of outputPaths) {
      rmSync(outputPath, {force: true});
    }
  };
  clean();
  try {
    return generate();
  } catch (error) {
    clean();
    throw error;
  }
};

export const validateNarrationDuration = (durationSeconds: number): string[] =>
  Number.isFinite(durationSeconds) &&
  durationSeconds > 0 &&
  durationSeconds < 59.5
    ? []
    : [
        `narration must be shorter than 59.5 seconds (received ${durationSeconds})`,
      ];

export const validateNarrationFileSize = (sizeBytes: number): string[] =>
  Number.isFinite(sizeBytes) && sizeBytes > 100_000
    ? []
    : [
        `narration must be larger than 100000 bytes (received ${sizeBytes})`,
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
