import {describe, expect, it} from 'vitest';
import {buildDeliveryManifest} from '../scripts/package-output';

describe('demo delivery manifest', () => {
  it('records the verified artifact hash, size, and stream contract', () => {
    expect(buildDeliveryManifest({
      probe: {
        format: {duration: '60.053333'},
        streams: [
          {
            codec_type: 'video',
            codec_name: 'h264',
            width: 1920,
            height: 1080,
            r_frame_rate: '30/1',
            pix_fmt: 'yuv420p',
          },
          {
            codec_type: 'audio',
            codec_name: 'aac',
            sample_rate: '48000',
            channels: 2,
          },
        ],
      },
      sha256: 'abc123',
      sizeBytes: 13_200_429,
    })).toEqual({
      schemaVersion: 1,
      artifact: 'freshsense-recruiter-demo-60s.mp4',
      sha256: 'abc123',
      sizeBytes: 13_200_429,
      durationSeconds: 60.053333,
      video: {
        codec: 'h264',
        width: 1920,
        height: 1080,
        fps: '30/1',
        pixelFormat: 'yuv420p',
      },
      audio: {
        codec: 'aac',
        sampleRateHz: 48000,
        channels: 2,
      },
    });
  });
});
