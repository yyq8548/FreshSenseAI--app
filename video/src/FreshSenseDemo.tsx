import type {Caption} from '@remotion/captions';
import {Audio} from '@remotion/media';
import {useCallback, useEffect, useState} from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useDelayRender,
} from 'remotion';
import {CaptionTrack} from './components/CaptionTrack';
import {ClosingCard} from './components/ClosingCard';
import {ScreenshotScene} from './components/ScreenshotScene';
import {TitleCard} from './components/TitleCard';
import {SCENES, type Scene} from './content';
import {theme} from './theme';

export const getManagerSwitchOpacity = (frame: number) => interpolate(frame, [60, 90], [0, 1], {
  extrapolateLeft: 'clamp',
  extrapolateRight: 'clamp',
});

const ManagerScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const switchOpacity = getManagerSwitchOpacity(frame);

  return <AbsoluteFill style={{background: theme.warmWhite, padding: `${theme.safeY}px ${theme.safeX}px`}}>
    <div style={{font: `700 68px ${theme.font}`, color: theme.charcoal, marginBottom: 24}}>{scene.headline}</div>
    <div style={{position: 'relative', flex: 1, overflow: 'hidden', borderRadius: 18, border: `1px solid ${theme.line}`, boxShadow: '0 18px 50px rgba(32,37,33,0.12)'}}>
      <Img src={staticFile('screens/manager-chat.png')} style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', opacity: 1 - switchOpacity}} />
      <Img src={staticFile('screens/daily-report.png')} style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', opacity: switchOpacity}} />
    </div>
  </AbsoluteFill>;
};

const SceneRenderer: React.FC<{scene: Scene}> = ({scene}) => {
  const component = sceneComponentName(scene);
  if (component === 'title') return <TitleCard />;
  if (component === 'closing') return <ClosingCard />;
  if (component === 'manager') return <ManagerScene scene={scene} />;
  return <ScreenshotScene scene={scene} />;
};

export const sceneComponentName = (scene: Scene): Scene['kind'] => scene.kind;

export const FreshSenseDemo: React.FC<{captionFile: string}> = ({captionFile}) => {
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const {delayRender, continueRender, cancelRender} = useDelayRender();
  const [handle] = useState(() => delayRender('Loading FreshSense captions'));
  const loadCaptions = useCallback(async () => {
    try {
      const response = await fetch(staticFile(captionFile));
      if (!response.ok) throw new Error(`Caption request failed with ${response.status}`);
      setCaptions(await response.json() as Caption[]);
      continueRender(handle);
    } catch (error) {
      cancelRender(error instanceof Error ? error : new Error(String(error)));
    }
  }, [cancelRender, captionFile, continueRender, handle]);

  useEffect(() => {
    void loadCaptions();
  }, [loadCaptions]);

  if (!captions) return null;

  return <AbsoluteFill style={{background: theme.warmWhite}}>
    <Audio src={staticFile('audio/narration.wav')} volume={1} />
    <Audio src={staticFile('audio/ambient.wav')} volume={0.10} />
    {SCENES.map((scene) => <Sequence key={scene.id} from={scene.startFrame} durationInFrames={scene.endFrame - scene.startFrame}>
      <SceneRenderer scene={scene} />
    </Sequence>)}
    <CaptionTrack captions={captions} />
  </AbsoluteFill>;
};
