import {execFileSync} from 'node:child_process';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {getRemotionInvocation} from '../src/media';

type ProbeStream = {
  codec_type?: string;
  codec_name?: string;
  width?: number;
  height?: number;
  r_frame_rate?: string;
  pix_fmt?: string;
};

export type ProbeResult = {
  format: {duration?: string};
  streams: ProbeStream[];
};

export const validateProbe = (probe: ProbeResult): string[] => {
  const errors: string[] = [];
  const duration = Number(probe.format.duration);
  const video = probe.streams.find((stream) => stream.codec_type === 'video');
  const audio = probe.streams.find((stream) => stream.codec_type === 'audio');

  if (!Number.isFinite(duration) || duration < 58 || duration > 62) {
    errors.push('duration must be between 58 and 62 seconds');
  }
  if (!video) {
    errors.push('video stream is missing');
  }
  if (video && (
    video.codec_name !== 'h264'
    || video.width !== 1920
    || video.height !== 1080
    || video.r_frame_rate !== '30/1'
    || video.pix_fmt !== 'yuv420p'
  )) {
    errors.push('video stream does not match the 1080p H.264 contract');
  }
  if (!audio) {
    errors.push('audio stream is missing');
  } else if (audio.codec_name !== 'aac') {
    errors.push('audio stream must use AAC');
  }

  return errors;
};

export const getProbeInvocation = (
  videoRoot: string,
  nodeExecutable: string,
  output: string,
): {command: string; args: string[]} => {
  const remotion = getRemotionInvocation(videoRoot, nodeExecutable);
  return {
    command: remotion.command,
    args: [
      ...remotion.prefixArgs,
      'ffprobe',
      '-v',
      'error',
      '-print_format',
      'json',
      '-show_streams',
      '-show_format',
      output,
    ],
  };
};

const isDirectInvocation = (): boolean => {
  if (!process.argv[1]) return false;
  return resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase();
};

if (isDirectInvocation()) {
  const videoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const output = resolve(videoRoot, '..', 'docs', 'demo', 'freshsense-recruiter-demo-60s.mp4');
  const invocation = getProbeInvocation(videoRoot, process.execPath, output);
  const stdout = execFileSync(invocation.command, invocation.args, {
    encoding: 'utf8',
  });
  const errors = validateProbe(JSON.parse(stdout) as ProbeResult);
  if (errors.length > 0) {
    for (const error of errors) console.error(error);
    process.exit(1);
  }
  console.log('FreshSense recruiter demo media contract passed.');
}
