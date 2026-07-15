import { createHash } from "node:crypto";
import {
  copyFile,
  mkdir,
  readFile,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

const STORY_FILES = Object.freeze({
  "US-01": "01-curious-newcomer",
  "US-02": "02-goal-led-discovery",
  "US-03": "03-changes-mind",
  "US-04": "04-hybrid-cart-management",
  "US-05": "05-thoughtful-checkout",
});

const artifactRoot = process.argv[2];
if (artifactRoot === undefined || artifactRoot.trim().length === 0) {
  throw new Error("Usage: node collect-human-story-artifacts.mjs <artifact-root>");
}

const absoluteRoot = path.resolve(artifactRoot);
const reportPath = path.join(absoluteRoot, "playwright-report.json");
const report = JSON.parse(await readFile(reportPath, "utf8"));
const specs = [];
for (const suite of report.suites ?? []) visitSuite(suite, specs);

const videoDir = path.join(absoluteRoot, "videos");
await mkdir(videoDir, { recursive: true });
const rows = [];

for (const [storyId, stableName] of Object.entries(STORY_FILES)) {
  const matches = specs.filter((spec) => spec.title.startsWith(`${storyId} `));
  if (matches.length !== 1) {
    throw new Error(`Expected one report spec for ${storyId}, found ${matches.length}.`);
  }
  const spec = matches[0];
  const tests = spec.tests ?? [];
  if (tests.length !== 1) {
    throw new Error(`Expected one project result for ${storyId}, found ${tests.length}.`);
  }
  const results = tests[0].results ?? [];
  if (results.length !== 1) {
    throw new Error(`Expected one non-retried result for ${storyId}, found ${results.length}.`);
  }
  const result = results[0];
  const videos = (result.attachments ?? []).filter(
    (attachment) => attachment.contentType === "video/webm" && attachment.path,
  );
  if (videos.length !== 1) {
    throw new Error(`Expected one video attachment for ${storyId}, found ${videos.length}.`);
  }

  const videoSource = path.resolve(videos[0].path);
  const videoTarget = path.join(videoDir, `${stableName}.webm`);
  await copyFile(videoSource, videoTarget);
  const evidencePath = path.join(absoluteRoot, "evidence", `${stableName}.json`);
  const videoMeasurement = await measurement(videoTarget);
  const evidenceMeasurement = await measurement(evidencePath);
  const evidence = JSON.parse(await readFile(evidencePath, "utf8"));
  if (evidence.story_id !== storyId) {
    throw new Error(`${storyId} evidence declares ${String(evidence.story_id)}.`);
  }

  rows.push({
    story_id: storyId,
    title: spec.title,
    playwright_status: result.status,
    duration_ms: result.duration,
    video_path: relativePath(videoTarget),
    video_byte_count: videoMeasurement.byteCount,
    video_sha256: videoMeasurement.sha256,
    evidence_path: relativePath(evidencePath),
    evidence_byte_count: evidenceMeasurement.byteCount,
    evidence_sha256: evidenceMeasurement.sha256,
  });
}

if (rows.length !== 5) {
  throw new Error(`Expected five collected stories, found ${rows.length}.`);
}

const manifest = {
  schema_version: 1,
  viewport: { width: 1920, height: 1080 },
  video_size: { width: 1920, height: 1080 },
  story_count: rows.length,
  stories: rows,
};
await writeFile(
  path.join(absoluteRoot, "assessment-manifest.json"),
  `${JSON.stringify(manifest, null, 2)}\n`,
  "utf8",
);

process.stdout.write(
  `${JSON.stringify({ story_count: rows.length, video_count: rows.length, evidence_count: rows.length })}\n`,
);

function visitSuite(suite, target) {
  for (const spec of suite.specs ?? []) target.push(spec);
  for (const child of suite.suites ?? []) visitSuite(child, target);
}

async function measurement(filePath) {
  const info = await stat(filePath);
  if (!info.isFile() || info.size <= 0) {
    throw new Error(`Artifact is absent or empty: ${filePath}`);
  }
  const bytes = await readFile(filePath);
  return {
    byteCount: bytes.byteLength,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

function relativePath(filePath) {
  return path.relative(absoluteRoot, filePath).replaceAll(path.sep, "/");
}
