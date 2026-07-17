import { createReadStream, statSync } from "node:fs";
import http from "node:http";
import path from "node:path";

import { chromium } from "@playwright/test";

const videoPath = process.env.VIDEO_PATH;
const frameRoot = process.env.FRAME_ROOT;
if (!videoPath || !frameRoot) {
  throw new Error("VIDEO_PATH and FRAME_ROOT are required.");
}

const server = http.createServer((request, response) => {
  if (request.url !== "/video.webm") {
    response.writeHead(200, { "content-type": "text/html" });
    response.end(
      '<style>*{box-sizing:border-box}html,body{margin:0;background:#000;overflow:hidden}video{display:block;width:1920px;height:1080px}</style><video src="/video.webm"></video>',
    );
    return;
  }

  const size = statSync(videoPath).size;
  const range = request.headers.range;
  if (!range) {
    response.writeHead(200, {
      "content-type": "video/webm",
      "content-length": size,
      "accept-ranges": "bytes",
    });
    createReadStream(videoPath).pipe(response);
    return;
  }

  const match = /bytes=(\d+)-(\d*)/.exec(range);
  if (!match) {
    response.writeHead(416);
    response.end();
    return;
  }
  const start = Number(match[1]);
  const end = match[2] ? Number(match[2]) : size - 1;
  response.writeHead(206, {
    "content-type": "video/webm",
    "content-length": end - start + 1,
    "content-range": `bytes ${start}-${end}/${size}`,
    "accept-ranges": "bytes",
  });
  createReadStream(videoPath, { start, end }).pipe(response);
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();
if (!address || typeof address === "string") {
  throw new Error("Video inspector did not bind a TCP port.");
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`http://127.0.0.1:${address.port}/`);
  const video = page.locator("video");
  const metadata = await video.evaluate(
    (element) =>
      new Promise((resolve, reject) => {
        const ready = () =>
          resolve({
            width: element.videoWidth,
            height: element.videoHeight,
            duration: element.duration,
          });
        if (element.readyState >= 1) {
          ready();
          return;
        }
        element.addEventListener("loadedmetadata", ready, { once: true });
        element.addEventListener(
          "error",
          () => reject(new Error("Recorded WebM could not load.")),
          { once: true },
        );
      }),
  );

  const times = [5, metadata.duration * 0.5, Math.max(0, metadata.duration - 3)];
  const names = [
    "validation-early.png",
    "validation-middle.png",
    "validation-final.png",
  ];
  for (let index = 0; index < times.length; index += 1) {
    await video.evaluate(
      (element, time) =>
        new Promise((resolve, reject) => {
          element.addEventListener("seeked", () => resolve(undefined), {
            once: true,
          });
          element.addEventListener(
            "error",
            () => reject(new Error("Recorded WebM seek failed.")),
            { once: true },
          );
          element.currentTime = time;
        }),
      times[index],
    );
    await video.screenshot({ path: path.join(frameRoot, names[index]) });
  }

  process.stdout.write(`${JSON.stringify({ metadata, frames: names })}\n`);
} finally {
  await browser.close();
  server.close();
}
