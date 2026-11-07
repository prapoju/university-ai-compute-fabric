import { expect, test } from '@playwright/test';

// Smoke: the real app process (playwright.config.ts webServer) is up and serves the liveness probe.
test('GET /healthz reports the process is up', async ({ request }) => {
  const response = await request.get('/healthz');

  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: 'ok' });
});
