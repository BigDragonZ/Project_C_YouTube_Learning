#!/usr/bin/env -S deno run --allow-net --allow-read --allow-write --allow-run --allow-env
/**
 * Download a single YouTube video/playlist item using yt-dlp with Chrome cookies.
 *
 * Usage:
 *   deno run --allow-net --allow-read --allow-write --allow-run --allow-env flow/script/download_youtube.ts <URL>
 *
 * Environment:
 *   - Uses project .venv yt-dlp (NEVER system Python yt-dlp)
 *   - Requires Chrome cookies for YouTube authentication
 */

const DOWNLOAD_DIR = "/tmp/video_audio_downloads";
const YTDLP_PATH = new URL("../../.venv/bin/yt-dlp", import.meta.url).pathname;

function ensureDir(path: string) {
  try {
    Deno.mkdirSync(path, { recursive: true });
  } catch { /* ignore */ }
}

async function runYtDlp(url: string): Promise<string> {
  ensureDir(DOWNLOAD_DIR);

  const args = [
    "--cookies-from-browser", "chrome",
    "--playlist-items", "1",
    "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "--merge-output-format", "mp4",
    "--output", `${DOWNLOAD_DIR}/%(title)s.%(ext)s`,
    "--no-warnings",
    url,
  ];

  console.log(`[INFO] yt-dlp ${args.join(" ")}`);

  const cmd = new Deno.Command(YTDLP_PATH, {
    args,
    stdout: "piped",
    stderr: "piped",
  });

  const { code, stdout, stderr } = await cmd.output();
  const out = new TextDecoder().decode(stdout);
  const err = new TextDecoder().decode(stderr);

  if (code !== 0) {
    throw new Error(`yt-dlp exited ${code}\n${err}`);
  }

  // Try to extract the final file path from yt-dlp output
  const destMatch = out.match(/\[download\] Destination: (.+)/m) ||
    err.match(/\[download\] Destination: (.+)/m);
  if (destMatch) return destMatch[1].trim();

  // Fallback: list newest file in download dir
  const files: string[] = [];
  for await (const entry of Deno.readDir(DOWNLOAD_DIR)) {
    if (entry.isFile) files.push(entry.name);
  }
  if (files.length === 0) throw new Error("No file found after download");

  files.sort((a, b) => {
    const sa = Deno.statSync(`${DOWNLOAD_DIR}/${a}`).mtime ?? new Date(0);
    const sb = Deno.statSync(`${DOWNLOAD_DIR}/${b}`).mtime ?? new Date(0);
    return sb.getTime() - sa.getTime();
  });
  return `${DOWNLOAD_DIR}/${files[0]}`;
}

// ── main ──────────────────────────────────────────────────────────────
const url = Deno.args[0];
if (!url) {
  console.error("Usage: download_youtube.ts <YOUTUBE_URL>");
  Deno.exit(1);
}

console.log(`[INFO] Target URL: ${url}`);
console.log(`[INFO] Download dir: ${DOWNLOAD_DIR}`);
console.log(`[INFO] yt-dlp: ${YTDLP_PATH}`);

try {
  const saved = await runYtDlp(url);
  console.log(`[SUCCESS] Saved to: ${saved}`);
  Deno.exit(0);
} catch (e: any) {
  console.error(`[ERROR] ${e.message}`);
  Deno.exit(1);
}
