import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import type {Scene} from '../content';
import {getScreenshotMotion} from '../motion';
import {theme} from '../theme';
import {Callout} from './Callout';

export const ScreenshotScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const duration = scene.endFrame - scene.startFrame;
  const motion = getScreenshotMotion(frame, duration);
  if (!scene.screenshot) throw new Error(`${scene.id} has no screenshot`);
  return <AbsoluteFill style={{background: theme.warmWhite, padding: `${theme.safeY}px ${theme.safeX}px`}}>
    <div style={{font: `700 68px ${theme.font}`, color: theme.charcoal, marginBottom: 24}}>{scene.headline}</div>
    <div style={{position: 'relative', flex: 1, overflow: 'hidden', borderRadius: 18, border: `1px solid ${theme.line}`, boxShadow: '0 18px 50px rgba(32,37,33,0.12)', opacity: motion.opacity}}>
      <Img src={staticFile(`screens/${scene.screenshot}`)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center', scale: motion.scale, translate: `${motion.x}px 0`}} />
      {scene.callouts.map((item) => <Callout key={item.label} data={item} />)}
    </div>
  </AbsoluteFill>;
};
