import { existsSync } from 'node:fs';
import { defineConfig } from '@playwright/test';

// E2E runner for Module 12. The pytest harness (tests/, pytest.ini) stays the primary suite;
// this config only drives tests/e2e/*.spec.ts against a real uvicorn process.
//
// No waitForTimeout anywhere (docs/impl2-rules.md): use web-first assertions instead.
// `make e2e` greps tests/e2e for it and fails the target.

// The repo venv when present (local), else python3 (CI installs into the system interpreter).
const python = process.env.PY ?? (existsSync('.venv/bin/python') ? '.venv/bin/python' : 'python3');

export default defineConfig({
  testDir: 'tests/e2e',
  retries: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
  },
  webServer: {
    command: `${python} -m uvicorn src.adapters.inbound.app:create_app --factory --host 127.0.0.1 --port 8000`,
    url: 'http://127.0.0.1:8000/healthz',
    env: { M12_DB_PATH: ':memory:' },
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
