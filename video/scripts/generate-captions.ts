import {execFileSync} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {
  downloadWhisperModel,
  installWhisperCpp,
  toCaptions,
  transcribe,
} from '@remotion/install-whisper-cpp';
import {NARRATION_TEXT} from '../src/content';
import {
  getRemotionInvocation,
  mergeZeroDurationCaptions,
  retimeCaptionsToNarration,
  validateCaptions,
} from '../src/media';

const whisperVersion = '1.5.5';
const whisperModel = 'small.en' as const;
const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const remotion = getRemotionInvocation(videoRoot);
const whisperRoot = join(videoRoot, 'whisper.cpp');
const tempRoot = join(videoRoot, '.tmp');
const captionRoot = join(videoRoot, 'public', 'captions');
const input = join(videoRoot, 'public', 'audio', 'narration.wav');
const converted = join(tempRoot, 'narration-16k.wav');

mkdirSync(tempRoot, {recursive: true});
mkdirSync(captionRoot, {recursive: true});
execFileSync(
  remotion.command,
  [
    ...remotion.prefixArgs,
    'ffmpeg',
    '-i',
    input,
    '-ar',
    '16000',
    '-ac',
    '1',
    converted,
    '-y',
  ],
  {stdio: 'inherit'},
);
await installWhisperCpp({to: whisperRoot, version: whisperVersion});
await downloadWhisperModel({model: whisperModel, folder: whisperRoot});
const whisperCppOutput = await transcribe({
  model: whisperModel,
  whisperPath: whisperRoot,
  whisperCppVersion: whisperVersion,
  inputPath: converted,
  tokenLevelTimestamps: true,
});
const {captions: rawCaptions} = toCaptions({whisperCppOutput});
const timingCaptions = mergeZeroDurationCaptions(rawCaptions);
const timingErrors = validateCaptions(timingCaptions);
if (timingErrors.length > 0) {
  throw new Error(timingErrors.join('\n'));
}
const captions = retimeCaptionsToNarration(timingCaptions, NARRATION_TEXT);
const captionErrors = validateCaptions(captions);
if (captionErrors.length > 0) {
  throw new Error(captionErrors.join('\n'));
}
writeFileSync(
  join(captionRoot, 'narration.json'),
  `${JSON.stringify(captions, null, 2)}\n`,
  'utf8',
);
console.log(`Generated ${captions.length} timed captions.`);
