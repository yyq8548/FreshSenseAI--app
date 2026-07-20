import {execFileSync} from 'node:child_process';
import {mkdirSync, statSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {NARRATION_TEXT} from '../src/content';

const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tempRoot = join(videoRoot, '.tmp');
const audioRoot = join(videoRoot, 'public', 'audio');
const textPath = join(tempRoot, 'narration.txt');
const outputPath = join(audioRoot, 'narration.wav');
const scriptPath = join(videoRoot, 'scripts', 'generate-voiceover.ps1');
const voice =
  process.env.FRESHSENSE_DEMO_VOICE ?? 'Microsoft Zira Desktop';

mkdirSync(tempRoot, {recursive: true});
mkdirSync(audioRoot, {recursive: true});
writeFileSync(textPath, NARRATION_TEXT, 'utf8');
execFileSync(
  'powershell.exe',
  [
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    scriptPath,
    '-TextPath',
    textPath,
    '-OutputPath',
    outputPath,
    '-VoiceName',
    voice,
  ],
  {stdio: 'inherit'},
);
if (statSync(outputPath).size <= 100_000) {
  throw new Error('Narration output is missing or too small.');
}
console.log(`Generated narration with ${voice}: ${outputPath}`);
