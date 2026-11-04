// Local adapter for pinned MIT @audio/denoise-declick 0.4.0. No networking.
import fs from 'node:fs';
import declick from '@audio/denoise-declick';

const [input, output, rate, channelCount, threshold = '8'] = process.argv.slice(2);
const channels = Number(channelCount), fsample = Number(rate), sensitivity = Number(threshold);
if (!Number.isInteger(channels) || channels < 1 || !Number.isInteger(fsample) || fsample < 8000 || !Number.isFinite(sensitivity) || sensitivity < 3 || sensitivity > 20) throw Error('Invalid audio format/settings');
const bytes = fs.readFileSync(input);
if (bytes.length % (4 * channels)) throw Error('Invalid f32 interleaved audio');
const samples = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.length/4);
const frames = samples.length/channels;
for (const v of samples) if (!Number.isFinite(v)) throw Error('Non-finite source');
const started = performance.now(), cpu = process.cpuUsage();
let changed = 0;
const result = Float32Array.from(samples);
for (let c = 0; c < channels; c++) {
  const mono = new Float32Array(frames);
  for (let i = 0; i < frames; i++) mono[i] = samples[i*channels+c];
  const fixed = declick(mono, { fs:fsample, threshold:sensitivity, longest:6 });
  if (fixed.length !== frames) throw Error('Changed audio duration');
  for (let i = 0; i < frames; i++) {
    if (!Number.isFinite(fixed[i])) throw Error('Non-finite repair');
    if (fixed[i] !== mono[i]) changed++;
    result[i*channels+c] = fixed[i];
  }
}
fs.writeFileSync(output, Buffer.from(result.buffer));
const used = process.cpuUsage(cpu);
console.log(JSON.stringify({ engine:'audiojs_ar_posterior', version:'0.4.0', lpc_version:'1.2.0', threshold:sensitivity,
  longest_ms:6, frames, channels, rate:fsample, changed_channel_samples:changed,
  wall_seconds:(performance.now()-started)/1000, cpu_core_seconds:(used.user+used.system)/1e6,
  peak_process_bytes:process.resourceUsage().maxRSS*1024 }));
