import {createTikTokStyleCaptions, type Caption} from '@remotion/captions';
import {useMemo} from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {theme} from '../theme';

export const CaptionTrack: React.FC<{captions: readonly Caption[]}> = ({captions}) => {
  const {fps} = useVideoConfig();
  const {pages} = useMemo(() => createTikTokStyleCaptions({
    captions: [...captions],
    combineTokensWithinMilliseconds: 1800,
  }), [captions]);

  return <AbsoluteFill style={{pointerEvents: 'none'}}>
    {pages.map((page, index) => {
      const next = pages[index + 1];
      const from = Math.round(page.startMs / 1000 * fps);
      const end = Math.round(Math.min(next?.startMs ?? 60000, page.startMs + 1800) / 1000 * fps);
      return <Sequence key={`${page.startMs}-${index}`} from={from} durationInFrames={Math.max(1, end - from)}>
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', padding: `0 ${theme.safeX + 100}px 110px`}}>
          <div style={{maxWidth: 1460, borderRadius: 12, padding: '14px 24px', background: 'rgba(32,37,33,0.92)', color: '#FFFFFF', font: `600 42px/1.25 ${theme.font}`, textAlign: 'center', whiteSpace: 'pre-wrap'}}>
            {page.tokens.map((token) => token.text).join('')}
          </div>
        </AbsoluteFill>
      </Sequence>;
    })}
  </AbsoluteFill>;
};
