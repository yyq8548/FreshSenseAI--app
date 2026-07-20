import {execFileSync} from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {NARRATION_TEXT} from '../src/content';
import {
  DEFAULT_EDGE_TTS_VOICE,
  getEdgeTtsInvocation,
  getNarrationFfmpegArgs,
  getRemotionInvocation,
  getSystemPythonExecutable,
  getVoicePythonExecutable,
  validateNarrationDuration,
  validateNarrationFileSize,
  withCleanOutputsSync,
} from '../src/media';

const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tempRoot = join(videoRoot, '.tmp');
const audioRoot = join(videoRoot, 'public', 'audio');
const textPath = join(tempRoot, 'narration.txt');
const compressedPath = join(tempRoot, 'narration.mp3');
const outputPath = join(audioRoot, 'narration.wav');
const requirementsPath = join(videoRoot, 'requirements-voice.txt');
const venvRoot = join(tempRoot, 'edge-tts-venv');
const voicePython = getVoicePythonExecutable(tempRoot);
const remotion = getRemotionInvocation(videoRoot);
const systemPython =
  process.env.FRESHSENSE_PYTHON ?? getSystemPythonExecutable();
const voice = process.env.FRESHSENSE_DEMO_VOICE ?? DEFAULT_EDGE_TTS_VOICE;

withCleanOutputsSync([compressedPath, outputPath], () => {
  mkdirSync(tempRoot, {recursive: true});
  mkdirSync(audioRoot, {recursive: true});
  writeFileSync(textPath, NARRATION_TEXT, 'utf8');
  if (!existsSync(voicePython)) {
    rmSync(venvRoot, {recursive: true, force: true});
    execFileSync(systemPython, ['-m', 'venv', venvRoot], {stdio: 'inherit'});
  }
  execFileSync(
    voicePython,
    [
      '-m',
      'pip',
      'install',
      '--disable-pip-version-check',
      '--requirement',
      requirementsPath,
    ],
    {stdio: 'inherit'},
  );
  const edgeTts = getEdgeTtsInvocation(
    voicePython,
    textPath,
    compressedPath,
    voice,
  );
  execFileSync(edgeTts.command, edgeTts.args, {stdio: 'inherit'});
  execFileSync(
    remotion.command,
    [
      ...remotion.prefixArgs,
      'ffmpeg',
      ...getNarrationFfmpegArgs(compressedPath, outputPath),
    ],
    {stdio: 'inherit'},
  );
  const sizeErrors = validateNarrationFileSize(statSync(outputPath).size);
  if (sizeErrors.length > 0) {
    throw new Error(sizeErrors.join('\n'));
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
  rmSync(compressedPath, {force: true});
});
