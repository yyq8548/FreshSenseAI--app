import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {basename, dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {
  getProbeInvocation,
  type ProbeResult,
  validateProbe,
} from './verify-output';

type DeliveryStream = ProbeResult['streams'][number] & {
  sample_rate?: string;
  channels?: number;
};

type DeliveryProbe = Omit<ProbeResult, 'streams'> & {
  streams: DeliveryStream[];
};

export type DeliveryManifest = {
  schemaVersion: 1;
  artifact: 'freshsense-recruiter-demo-60s.mp4';
  sha256: string;
  sizeBytes: number;
  durationSeconds: number;
  video: {
    codec: string;
    width: number;
    height: number;
    fps: string;
    pixelFormat: string;
  };
  audio: {
    codec: string;
    sampleRateHz: number;
    channels: number;
  };
};

export const buildDeliveryManifest = ({
  probe,
  sha256,
  sizeBytes,
}: {
  probe: DeliveryProbe;
  sha256: string;
  sizeBytes: number;
}): DeliveryManifest => {
  const errors = validateProbe(probe);
  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }
  const video = probe.streams.find((stream) => stream.codec_type === 'video');
  const audio = probe.streams.find((stream) => stream.codec_type === 'audio');
  if (!video || !audio) {
    throw new Error('Validated media streams are unavailable.');
  }
  return {
    schemaVersion: 1,
    artifact: 'freshsense-recruiter-demo-60s.mp4',
    sha256,
    sizeBytes,
    durationSeconds: Number(probe.format.duration),
    video: {
      codec: video.codec_name ?? '',
      width: video.width ?? 0,
      height: video.height ?? 0,
      fps: video.r_frame_rate ?? '',
      pixelFormat: video.pix_fmt ?? '',
    },
    audio: {
      codec: audio.codec_name ?? '',
      sampleRateHz: Number(audio.sample_rate),
      channels: audio.channels ?? 0,
    },
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
  const probe = JSON.parse(execFileSync(invocation.command, invocation.args, {
    encoding: 'utf8',
  })) as DeliveryProbe;
  const sha256 = createHash('sha256').update(readFileSync(output)).digest('hex');
  const manifest = buildDeliveryManifest({
    probe,
    sha256,
    sizeBytes: statSync(output).size,
  });
  const checksumPath = `${output}.sha256`;
  const manifestPath = resolve(dirname(output), 'freshsense-recruiter-demo-60s.json');
  writeFileSync(checksumPath, `${sha256} *${basename(output)}\n`, 'utf8');
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  console.log(`Packaged ${basename(output)} (${manifest.sizeBytes} bytes, SHA-256 ${sha256}).`);
}
