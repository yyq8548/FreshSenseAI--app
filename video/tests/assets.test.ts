import {mkdtempSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {describe, expect, it} from 'vitest';
import {readPngDimensions, syncScreens} from '../scripts/sync-assets';

const pngHeader = (width: number, height: number) => {
  const data = Buffer.alloc(24);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(data, 0);
  data.writeUInt32BE(width, 16);
  data.writeUInt32BE(height, 20);
  return data;
};

describe('approved screenshot assets', () => {
  it('reads PNG dimensions from the IHDR header', () => {
    const root = mkdtempSync(join(tmpdir(), 'freshsense-png-'));
    const file = join(root, 'screen.png');
    writeFileSync(file, pngHeader(1920, 1080));
    expect(readPngDimensions(file)).toEqual({width: 1920, height: 1080});
  });

  it('copies every required screen into the Remotion public folder', () => {
    const root = mkdtempSync(join(tmpdir(), 'freshsense-assets-'));
    const repo = join(root, 'repo');
    const video = join(repo, 'video');
    mkdirSync(join(repo, 'docs', 'images', 'workbench'), {recursive: true});
    for (const name of ['overview.png', 'batch-inspection.png', 'review-queue.png', 'agent-activity.png', 'manager-chat.png', 'daily-report.png']) {
      writeFileSync(join(repo, 'docs', 'images', 'workbench', name), pngHeader(1920, 1080));
    }
    syncScreens(repo, video);
    expect(readFileSync(join(video, 'public', 'screens', 'manager-chat.png'))).toEqual(pngHeader(1920, 1080));
  });
});
