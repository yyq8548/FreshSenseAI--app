import {describe, expect, it} from 'vitest';
import {readFileSync} from 'node:fs';
import {SCENES, TOTAL_FRAMES} from '../src/content';
import {getManagerSwitchOpacity, sceneComponentName} from '../src/FreshSenseDemo';
import {getRemotionStillCommand} from '../scripts/render-stills';

describe('composition contract', () => {
  it('uses one sequence per scene and the approved final duration', () => {
    expect(SCENES).toHaveLength(8);
    expect(SCENES.reduce((sum, scene) => sum + scene.endFrame - scene.startFrame, 0)).toBe(TOTAL_FRAMES);
  });

  it('aligns scene cuts to the approved neural narration sentences', () => {
    expect(SCENES.map(({startFrame, endFrame}) => [startFrame, endFrame])).toEqual([
      [0, 150],
      [150, 252],
      [252, 585],
      [585, 836],
      [836, 1119],
      [1119, 1194],
      [1194, 1326],
      [1326, 1800],
    ]);
  });

  it('uses only approved screenshots', () => {
    expect([...new Set(SCENES.flatMap((scene) => scene.screenshot ? [scene.screenshot] : []))]).toEqual([
      'overview.png', 'batch-inspection.png', 'agent-activity.png', 'review-queue.png', 'manager-chat.png',
    ]);
  });

  it('maps every scene to its approved visual component', () => {
    expect(SCENES.map(sceneComponentName)).toEqual([
      'title', 'screenshot', 'screenshot', 'screenshot', 'screenshot', 'screenshot', 'manager', 'closing',
    ]);
  });

  it('invokes the local Remotion CLI through Node on Windows', () => {
    const command = getRemotionStillCommand(450);
    expect(command.executable).toBe(process.execPath);
    expect(command.args[0]).toMatch(/@remotion[\\/]cli[\\/]remotion-cli\.js$/);
    expect(command.args).toContain('450');
  });

  it('completes the manager-to-report crossfade before the review frame', () => {
    expect(getManagerSwitchOpacity(59)).toBe(0);
    expect(getManagerSwitchOpacity(90)).toBe(1);
  });

  it('shows the human-review callout early in its short scene', () => {
    expect(SCENES.find((scene) => scene.id === 'review')?.callouts[0]?.delayFrame).toBe(8);
  });

  it('renders through PNG intermediates in the BT.709 broadcast color space', () => {
    const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as {scripts: {render: string}};
    expect(packageJson.scripts.render).toContain('--image-format=png');
    expect(packageJson.scripts.render).toContain('--color-space=bt709');
  });
});
