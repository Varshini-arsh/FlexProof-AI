import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const python = process.env.FLEXPROOF_PYTHON ?? "python";
const externalBaseURL = process.env.FLEXPROOF_DOCKER_URL;

export default defineConfig({
  testDir: "./e2e", workers: 1, timeout: 30_000,
  reporter: "list",
  use: {
    baseURL: externalBaseURL ?? "http://127.0.0.1:5175", viewport: { width: 1440, height: 1000 },
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    screenshot: "only-on-failure", trace: "retain-on-failure",
  },
  webServer: externalBaseURL ? [] : [
    {
      command: `"${python}" -m alembic upgrade head && "${python}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010`,
      cwd: root, url: "http://127.0.0.1:8010/api/health", reuseExistingServer: false,
      env: { PYTHONPATH: root, DATABASE_URL: "sqlite:///./e2e-flexproof.sqlite3", FLEXPROOF_CORS_ORIGINS: "http://127.0.0.1:5175" },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5175 --strictPort",
      url: "http://127.0.0.1:5175", reuseExistingServer: false,
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8010/api" },
    },
  ],
});
