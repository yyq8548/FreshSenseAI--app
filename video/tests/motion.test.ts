import {describe, expect, it} from 'vitest';
import {getScreenshotMotion} from '../src/motion';

describe('documentary screenshot motion', () => {
  it('starts at full size and ends with a restrained zoom', () => {
    expect(getScreenshotMotion(0, 300)).toEqual({scale: 1, x: 0, opacity: 0});
    const end = getScreenshotMotion(299, 300);
    expect(end.scale).toBeGreaterThan(1.035);
    expect(end.scale).toBeLessThanOrEqual(1.04);
    expect(end.opacity).toBeLessThan(0.1);
  });

  it('is fully visible through the middle of a scene', () => {
    expect(getScreenshotMotion(150, 300).opacity).toBe(1);
  });
});
