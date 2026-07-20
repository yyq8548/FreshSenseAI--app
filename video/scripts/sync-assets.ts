import {copyFileSync, existsSync, mkdirSync, readFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {REQUIRED_SCREENS} from '../src/assets';

export const readPngDimensions = (path: string) => {
  const header = readFileSync(path).subarray(0, 24);
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (header.length < 24 || !header.subarray(0, 8).equals(signature)) throw new Error(`${path} is not a PNG`);
  return {width: header.readUInt32BE(16), height: header.readUInt32BE(20)};
};

export const syncScreens = (repoRoot: string, videoRoot: string) => {
  const sourceRoot = join(repoRoot, 'docs', 'images', 'workbench');
  const destinationRoot = join(videoRoot, 'public', 'screens');
  mkdirSync(destinationRoot, {recursive: true});
  for (const name of REQUIRED_SCREENS) {
    const source = join(sourceRoot, name);
    if (!existsSync(source)) throw new Error(`Missing approved screenshot: ${source}`);
    const dimensions = readPngDimensions(source);
    if (dimensions.width < 1900 || dimensions.height < 1000) throw new Error(`${name} is too small for a 1080p crop`);
    copyFileSync(source, join(destinationRoot, name));
  }
};

if (resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  syncScreens(resolve(videoRoot, '..'), videoRoot);
  console.log(`Copied ${REQUIRED_SCREENS.length} approved screenshots.`);
}
