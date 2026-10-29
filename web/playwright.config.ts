// Playwright specs for the UI screens. Traces Lab owns the shared harness and CI wiring (CONTRACTS.md 6);
// this config only runs these specs locally against an already running web app and API.
//   TRACES_WEB_URL (default http://127.0.0.1:5173) must serve the app with /api proxied to a Traces API that has at least one snapshot.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: process.env.TRACES_WEB_URL ?? "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
    // Android phone class, 360 px wide (IA.md section 4).
    { name: "android-360", use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 } },
  ],
});
