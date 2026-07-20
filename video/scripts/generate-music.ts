import {execFileSync} from 'node:child_process';
import {mkdirSync, statSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {getAmbientFfmpegArgs, getRemotionInvocation} from '../src/media';

const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const remotion = getRemotionInvocation(videoRoot);
const audioRoot = join(videoRoot, 'public', 'audio');
const output = join(audioRoot, 'ambient.wav');
mkdirSync(audioRoot, {recursive: true});
execFileSync(
  remotion.command,
  [...remotion.prefixArgs, 'ffmpeg', ...getAmbientFfmpegArgs(output)],
  {stdio: 'inherit'},
);
if (statSync(output).size <= 100_000) {
  throw new Error('Ambient audio output is missing or too small.');
}
console.log(`Generated original ambient bed: ${output}`);
