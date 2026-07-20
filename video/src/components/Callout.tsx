import {interpolate, useCurrentFrame} from 'remotion';
import type {Callout as CalloutData} from '../content';
import {theme} from '../theme';

export const Callout: React.FC<{data: CalloutData}> = ({data}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [data.delayFrame, data.delayFrame + 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div style={{position: 'absolute', left: `${data.x}%`, top: `${data.y}%`, display: 'flex', alignItems: 'center', gap: 12, color: theme.charcoal, font: `700 34px ${theme.font}`, opacity: progress, translate: `${16 * (1 - progress)}px 0`}}>
    <span style={{width: 14, height: 14, borderRadius: 7, background: theme.green}} />
    <span style={{background: 'rgba(250,249,245,0.94)', border: `2px solid ${theme.green}`, borderRadius: 8, padding: '12px 18px'}}>{data.label}</span>
  </div>;
};
