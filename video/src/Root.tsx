import {Composition} from 'remotion';
import {FreshSenseDemo} from './FreshSenseDemo';
import {FPS, TOTAL_FRAMES} from './content';

export const RemotionRoot: React.FC = () => <Composition
  id="FreshSenseRecruiterDemo"
  component={FreshSenseDemo}
  durationInFrames={TOTAL_FRAMES}
  fps={FPS}
  width={1920}
  height={1080}
  defaultProps={{captionFile: 'captions/narration.json'}}
/>;
