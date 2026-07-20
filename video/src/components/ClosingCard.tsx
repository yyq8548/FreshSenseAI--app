import {AbsoluteFill} from 'remotion';
import {theme} from '../theme';
import {TechStack} from './TechStack';

export const ClosingCard: React.FC = () => <AbsoluteFill style={{background: theme.warmWhite, justifyContent: 'center', alignItems: 'center', color: theme.charcoal, gap: 36}}>
  <h1 style={{font: `700 86px ${theme.font}`, margin: 0}}>See FreshSense working</h1>
  <TechStack />
  <div style={{display: 'flex', gap: 56, font: `700 36px ${theme.font}`, color: theme.greenDark}}>
    <span>freshsenseai.com</span><span>github.com/yyq8548/FreshSenseAI--app</span>
  </div>
</AbsoluteFill>;
