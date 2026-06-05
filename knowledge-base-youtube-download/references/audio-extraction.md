# Audio Extraction Reference

Session: 2026-05-14 — Adding ffmpeg-based audio extraction to the knowledge pipeline.

## ffmpeg Parameters

| Flag | Value | Purpose |
|------|-------|---------|
| `-y` | — | Overwrite output without prompt |
| `-i` | input.mp4 | Input file |
| `-vn` | — | Disable video stream |
| `-ar` | 22050 | Audio sample rate (22.05 kHz) |
| `-ac` | 1 | Mono channel |
| `-b:a` | 64k | Audio bitrate |
| `-f` | mp3 | Output format |

## lib/audio.ts API

```ts
export interface ExtractOptions {
  inputPath: string;
  outputPath: string;
  sampleRate?: number;  // default 22050
  channels?: number;    // default 1 (mono)
  bitrate?: string;     // default "64k"
  format?: string;      // default "mp3"
}

export async function extractAudio(options: ExtractOptions): Promise<string>
export async function probeFile(path: string): Promise<{
  duration: number;
  bitrate: number;
  codec: string;
  sampleRate?: number;
}>
```

## Typical Compression Ratio

- Input: 19 MB MP4 (1080p AV1, ~5 min)
- Output: 2.3 MB MP3 (64k mono, 22kHz)
- Ratio: ~8:1

## Error Handling

- `ffmpeg exited N`: Check stderr for codec/format issues
- `Output file not found`: ffmpeg may have failed silently; verify input file is valid
- `ffprobe failed`: Input file may be corrupted or unsupported format

## Testing

```ts
Deno.test("probeFile returns valid metadata", async () => {
  const info = await probeFile("test.mp3");
  assertEquals(info.duration > 0, true);
  assertEquals(info.codec, "mp3");
});
```
