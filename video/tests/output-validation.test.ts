import {describe, expect, it} from 'vitest';
import {
  getProbeInvocation,
  validateProbe,
} from '../scripts/verify-output';

describe('final MP4 validation', () => {
  it('accepts the required H.264 video and audio streams', () => {
    expect(validateProbe({
      format: {duration: '60.0'},
      streams: [
        {
          codec_type: 'video',
          codec_name: 'h264',
          width: 1920,
          height: 1080,
          r_frame_rate: '30/1',
          pix_fmt: 'yuv420p',
        },
        {codec_type: 'audio', codec_name: 'aac'},
      ],
    })).toEqual([]);
  });

  it('rejects missing audio and an invalid duration', () => {
    expect(validateProbe({
      format: {duration: '70.0'},
      streams: [
        {
          codec_type: 'video',
          codec_name: 'h264',
          width: 1920,
          height: 1080,
          r_frame_rate: '30/1',
          pix_fmt: 'yuv420p',
        },
      ],
    })).toEqual([
      'duration must be between 58 and 62 seconds',
      'audio stream is missing',
    ]);
  });

  it('rejects invalid or incomplete video metadata', () => {
    expect(validateProbe({format: {duration: 'not-a-number'}, streams: []})).toEqual([
      'duration must be between 58 and 62 seconds',
      'video stream is missing',
      'audio stream is missing',
    ]);
  });

  it('invokes the local Remotion CLI through Node on Windows', () => {
    expect(getProbeInvocation('C:\\video', 'C:\\node.exe', 'C:\\demo.mp4')).toEqual({
      command: 'C:\\node.exe',
      args: [
        'C:\\video\\node_modules\\@remotion\\cli\\remotion-cli.js',
        'ffprobe',
        '-v',
        'error',
        '-print_format',
        'json',
        '-show_streams',
        '-show_format',
        'C:\\demo.mp4',
      ],
    });
  });
});
