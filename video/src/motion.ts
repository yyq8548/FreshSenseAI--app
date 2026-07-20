import {Easing, interpolate} from 'remotion';

export const getScreenshotMotion = (frame: number, duration: number) => ({
  scale: interpolate(frame, [0, duration - 1], [1, 1.04], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.55, 1)}),
  x: interpolate(frame, [0, duration - 1], [0, -18], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.55, 1)}),
  opacity: interpolate(frame, [0, 15, duration - 16, duration - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
});
