import { defineConfig, devices } from "@playwright/test";

// Smoke tests run the production build with no agent behind it, which exercises every page's
// "agent unavailable" path as well as layout, theming and keyboard access.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://localhost:3100" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "npm run start -- -p 3100",
    url: "http://localhost:3100",
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: { SHERPA_AGENT_URL: "http://127.0.0.1:9", SHERPA_API_KEY: "test" },
  },
});
