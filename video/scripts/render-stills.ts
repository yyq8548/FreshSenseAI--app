import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const frames = [0, 450, 900, 1350, 1770];

export const getRemotionStillCommand = (frame: number) => ({
  executable: process.execPath,
  args: [
    resolve('node_modules', '@remotion', 'cli', 'remotion-cli.js'),
    'still',
    'src/index.ts',
    'FreshSenseRecruiterDemo',
    `out/stills/frame-${frame}.png`,
    '--frame',
    String(frame),
    '--overwrite',
  ],
});

if (resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  mkdirSync(resolve('out', 'stills'), {recursive: true});
  for (const frame of frames) {
    const command = getRemotionStillCommand(frame);
    execFileSync(command.executable, command.args, {stdio: 'inherit'});
  }
}
