import {execFileSync} from 'node:child_process';
import {mkdirSync, rmSync, statSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {NARRATION_TEXT} from '../src/content';
import {
  getRemotionInvocation,
  validateNarrationDuration,
} from '../src/media';

const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tempRoot = join(videoRoot, '.tmp');
const audioRoot = join(videoRoot, 'public', 'audio');
const textPath = join(tempRoot, 'narration.txt');
const outputPath = join(audioRoot, 'narration.wav');
const scriptPath = join(videoRoot, 'scripts', 'generate-voiceover.ps1');
const remotion = getRemotionInvocation(videoRoot);
const voice =
  process.env.FRESHSENSE_DEMO_VOICE ?? 'Microsoft Zira Desktop';

mkdirSync(tempRoot, {recursive: true});
mkdirSync(audioRoot, {recursive: true});
writeFileSync(textPath, NARRATION_TEXT, 'utf8');
try {
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
  const probeOutput = execFileSync(
    remotion.command,
    [
      ...remotion.prefixArgs,
      'ffprobe',
      '-v',
      'error',
      '-show_entries',
      'format=duration',
      '-of',
      'default=noprint_wrappers=1',
      outputPath,
    ],
    {encoding: 'utf8'},
  );
  const duration = Number(probeOutput.match(/duration=([\d.]+)/)?.[1]);
  const durationErrors = validateNarrationDuration(duration);
  if (durationErrors.length > 0) {
    throw new Error(durationErrors.join('\n'));
  }
  console.log(
    `Generated narration with ${voice}: ${outputPath} (${duration.toFixed(6)}s)`,
  );
} catch (error) {
  rmSync(outputPath, {force: true});
  throw error;
}
