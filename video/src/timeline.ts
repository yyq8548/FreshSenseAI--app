import {SCENES, TOTAL_FRAMES, type Scene} from './content';

export const validateTimeline = (scenes: readonly Scene[]): string[] => {
  const errors: string[] = [];
  if (scenes.length === 0) return ['timeline has no scenes'];
  if (scenes[0].startFrame !== 0) errors.push('timeline must start at frame 0');
  scenes.forEach((scene, index) => {
    if (scene.endFrame <= scene.startFrame) errors.push(`${scene.id} has no duration`);
    if (index > 0 && scenes[index - 1].endFrame !== scene.startFrame) {
      errors.push(`${scene.id} does not touch the previous scene`);
    }
  });
  if (scenes.at(-1)?.endFrame !== TOTAL_FRAMES) errors.push('timeline must end at frame 1800');
  return errors;
};

export const sceneAtFrame = (frame: number): Scene => {
  const scene = SCENES.find((item) => frame >= item.startFrame && frame < item.endFrame);
  if (!scene) throw new Error(`No scene covers frame ${frame}`);
  return scene;
};
