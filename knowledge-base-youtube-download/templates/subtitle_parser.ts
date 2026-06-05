#!/usr/bin/env -S deno run --allow-net --allow-read --allow-write --allow-run --allow-env
/**
 * Template: Download YouTube subtitles and convert to Markdown.
 *
 * Copy this file, modify the URL / course / index, and run.
 */

import { dirname, join } from "https://deno.land/std@0.224.0/path/mod.ts";

const YTDLP_PATH = new URL("../../.venv/bin/yt-dlp", import.meta.url).pathname;
const PROJECT_ROOT = dirname(dirname(dirname(import.meta.url))).replace("file://", "");

function sanitizeFilename(name: string): string {
  return name.replace(/[<>:\"/\\|?*]/g, "_").trim();
}

async function fetchVideoTitle(url: string): Promise<string> {
  const cmd = new Deno.Command(YTDLP_PATH, {
    args: ["--cookies-from-browser", "chrome", "--no-warnings", "--print", "%(title)s", "--skip-download", url],
    stdout: "piped",
    stderr: "piped",
  });
  const { code, stdout, stderr } = await cmd.output();
  if (code !== 0) {
    throw new Error(`Failed to fetch title: ${new TextDecoder().decode(stderr)}`);
  }
  return new TextDecoder().decode(stdout).trim();
}

async function downloadSubtitle(url: string, basePath: string): Promise<string> {
  const cmd = new Deno.Command(YTDLP_PATH, {
    args: [
      "--cookies-from-browser", "chrome",
      "--no-warnings",
      "--write-auto-subs",
      "--skip-download",
      "--sub-langs", "en",
      "--convert-subs", "srt",
      "--output", basePath,
      url,
    ],
    stdout: "piped",
    stderr: "piped",
  });

  const { code, stderr } = await cmd.output();
  const err = new TextDecoder().decode(stderr);

  if (code !== 0 && !err.includes("Downloading")) {
    throw new Error(`yt-dlp exited ${code}: ${err}`);
  }

  const srtFile = `${basePath}.en.srt`;
  try {
    await Deno.stat(srtFile);
    return srtFile;
  } catch {
    const altFile = `${basePath}.srt`;
    await Deno.stat(altFile);
    return altFile;
  }
}

function parseSrt(content: string): Array<{ index: number; start: string; end: string; text: string }> {
  const blocks = content.trim().split(/\n\s*\n/);
  const entries: Array<{ index: number; start: string; end: string; text: string }> = [];

  for (const block of blocks) {
    const lines = block.trim().split("\n");
    if (lines.length < 3) continue;

    const idx = parseInt(lines[0].trim(), 10);
    if (isNaN(idx)) continue;

    const timeMatch = lines[1].match(/(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})/);
    if (!timeMatch) continue;

    const text = lines
      .slice(2)
      .join(" ")
      .replace(/\r/g, "")
      .replace(/<[^>]+>/g, "")
      .replace(/\[music\]|\[Music\]|\[音楽\]|♪/gi, "")
      .trim();

    if (!text) continue;

    entries.push({ index: idx, start: timeMatch[1], end: timeMatch[2], text });
  }

  return entries;
}

function srtToMarkdown(
  entries: Array<{ index: number; start: string; end: string; text: string }>,
  title: string,
  url: string,
  courseName: string,
  index: number
): string {
  const lines: string[] = [];
  lines.push(`# ${title}`);
  lines.push("");
  lines.push("## 元信息");
  lines.push("");
  lines.push(`- **序号**: ${index}`);
  lines.push(`- **课程**: ${courseName}`);
  lines.push(`- **链接**: ${url}`);
  lines.push(`- **处理时间**: ${new Date().toISOString().slice(0, 19).replace("T", " ")}`);
  lines.push(`- **来源**: YouTube 自动生成字幕`);
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push("## 字幕内容");
  lines.push("");

  for (const entry of entries) {
    lines.push(`**[${entry.start} - ${entry.end}]** ${entry.text}`);
    lines.push("");
  }

  return lines.join("\n");
}

// ── main ──────────────────────────────────────────────────────────────
const url = Deno.args[0] || "<YOUTUBE_URL>";
const courseName = Deno.args[1] || "<COURSE_NAME>";
const indexStr = Deno.args[2] || "1";

if (!url || url === "<YOUTUBE_URL>") {
  console.error("Usage: download_subtitles.ts <URL> <COURSE_NAME> <INDEX>");
  Deno.exit(1);
}

const index = parseInt(indexStr, 10);
const outDir = join(PROJECT_ROOT, "flow", courseName);
await Deno.mkdir(outDir, { recursive: true });

const title = await fetchVideoTitle(url);
const safeTitle = sanitizeFilename(title);
const filename = `${String(index).padStart(2, "0")}-${safeTitle}.md`;
const outputPath = join(outDir, filename);
const tempBase = join(outDir, `_tmp_${Date.now()}`);

const srtFile = await downloadSubtitle(url, tempBase);
const srtContent = await Deno.readTextFile(srtFile);
const entries = parseSrt(srtContent);
const markdown = srtToMarkdown(entries, title, url, courseName, index);

await Deno.writeTextFile(outputPath, markdown);
await Deno.remove(srtFile);
try { await Deno.remove(`${tempBase}.en.srt`); } catch { /* ignore */ }

console.log(`[SUCCESS] Markdown saved to: ${outputPath}`);
console.log(`[INFO] Total entries: ${entries.length}`);
