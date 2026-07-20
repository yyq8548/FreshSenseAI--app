import {describe, expect, it} from 'vitest';
import {NARRATION_TEXT, SCENES, TOTAL_FRAMES} from '../src/content';
import {sceneAtFrame, validateTimeline} from '../src/timeline';

describe('FreshSense timeline', () => {
  it('covers exactly 60 seconds at 30 fps without gaps', () => {
    expect(TOTAL_FRAMES).toBe(1800);
    expect(validateTimeline(SCENES)).toEqual([]);
    expect(SCENES.at(-1)?.endFrame).toBe(TOTAL_FRAMES);
  });

  it('keeps the approved eight story beats', () => {
    expect(SCENES.map((scene) => scene.id)).toEqual([
      'problem', 'overview', 'batch', 'vision', 'agent', 'review', 'manager', 'cta',
    ]);
  });

  it('keeps the 138-word approved narration', () => {
    expect(NARRATION_TEXT.trim().split(/\s+/)).toHaveLength(138);
  });

  it('resolves boundary frames to the correct scene', () => {
    expect(sceneAtFrame(0).id).toBe('problem');
    expect(sceneAtFrame(149).id).toBe('problem');
    expect(sceneAtFrame(150).id).toBe('overview');
    expect(sceneAtFrame(1799).id).toBe('cta');
  });
});
