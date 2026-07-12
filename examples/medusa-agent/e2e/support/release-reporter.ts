import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import type {
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

interface MeasuredTestResult {
  readonly title: string;
  readonly project: string;
  readonly status: TestResult["status"];
  readonly duration_ms: number;
  readonly retry: number;
  readonly error_count: number;
}

export default class ReleaseReporter implements Reporter {
  readonly #results: MeasuredTestResult[] = [];

  onTestEnd(test: TestCase, result: TestResult): void {
    this.#results.push({
      title: test.title,
      project: test.parent.project()?.name ?? "unknown",
      status: result.status,
      duration_ms: result.duration,
      retry: result.retry,
      error_count: result.errors.length,
    });
  }

  async onEnd(result: FullResult): Promise<void> {
    const bundleRoot = requiredEnvironment("ROUTEDECK_RELEASE_BUNDLE");
    const gate = requiredEnvironment("ROUTEDECK_E2E_REPORT_NAME");
    const directory = path.join(bundleRoot, "browser", "playwright-report");
    await mkdir(directory, { recursive: true });
    const failedCount = this.#results.filter(
      (test) => !["passed", "skipped"].includes(test.status),
    ).length;
    const passedCount = this.#results.filter(
      (test) => test.status === "passed",
    ).length;
    const skippedCount = this.#results.filter(
      (test) => test.status === "skipped",
    ).length;
    const status =
      result.status === "passed" && failedCount === 0 && passedCount > 0
        ? "pass"
        : "fail";
    await writeFile(
      path.join(directory, `${gate}.json`),
      `${JSON.stringify(
        {
          schema_version: 1,
          status,
          source: "playwright_reporter_callbacks",
          gate,
          full_result_status: result.status,
          test_count: this.#results.length,
          passed_count: passedCount,
          skipped_count: skippedCount,
          failed_count: failedCount,
          tests: this.#results,
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
  }
}

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.trim().length === 0) {
    throw new Error(`${name} is required for the release reporter.`);
  }
  return value;
}
