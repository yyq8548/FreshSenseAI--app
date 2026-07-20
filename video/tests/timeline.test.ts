import {describe, expect, it} from 'vitest';
import {
  APPROVED_NARRATION_TEXT,
  NARRATION_TEXT,
  SCENES,
  TOTAL_FRAMES,
} from '../src/content';
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

  it('keeps the 112-word final calibrated narration', () => {
    expect(NARRATION_TEXT.trim().split(/\s+/)).toHaveLength(112);
  });

  it('matches the exact approved final narration', () => {
    expect(APPROVED_NARRATION_TEXT).toBe(
      'Fruit checks happen fast, but the record often disappears with the shift. FreshSense gives grocery teams a shared inspection record. Staff can add a photo or batch of twenty. The model covers apples, bananas, oranges, mangoes, tomatoes, and pears. Photos are not stored by default. DenseNet201 looks for visible fresh or rotten patterns. A separate gate withholds unclear or unsupported inputs. A bounded Agent checks history and reviewed guidance, creates follow-up tasks, and notifies staff. High-risk actions require manager approval. Staff confirm or correct results. Managers ask grounded questions and check the daily report. FreshSense runs on Python, TensorFlow, FastAPI, React, PostgreSQL, and Azure. Try freshsenseai.com or view the code on GitHub.',
    );
    expect(NARRATION_TEXT).toBe(APPROVED_NARRATION_TEXT);
  });

  it('resolves boundary frames to the correct scene', () => {
    expect(sceneAtFrame(0).id).toBe('problem');
    expect(sceneAtFrame(149).id).toBe('problem');
    expect(sceneAtFrame(150).id).toBe('overview');
    expect(sceneAtFrame(1799).id).toBe('cta');
  });
});
