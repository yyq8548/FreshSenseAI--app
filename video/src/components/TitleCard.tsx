import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {theme} from '../theme';

export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{background: theme.warmWhite, justifyContent: 'center', alignItems: 'center', color: theme.charcoal}}>
    <div style={{width: 150, height: 8, background: theme.green, marginBottom: 36, opacity: interpolate(frame, [0, 20], [0, 1], {extrapolateRight: 'clamp'})}} />
    <h1 style={{font: `700 112px ${theme.font}`, margin: 0, opacity: interpolate(frame, [10, 42], [0, 1], {extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)})}}>FreshSense</h1>
    <p style={{font: `400 46px ${theme.font}`, color: theme.muted, margin: '28px 0 0'}}>AI-assisted fruit inspection for small grocery teams</p>
  </AbsoluteFill>;
};
