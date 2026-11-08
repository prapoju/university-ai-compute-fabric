import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

import { CopilotConsolePage } from './pages/CopilotConsolePage';

// Annex 12.6 (docs/task-impl2.md): Nadia diagnoses an access denial and copies the verified runbook.
// The expected runbook is the committed registry template, not a copy typed into this spec.
const runbook = JSON.parse(
  readFileSync(join(__dirname, '../../fixtures/runbooks/access-denial-not-in-allowlist.json'), 'utf-8'),
) as { steps: string[] };

test.use({ permissions: ['clipboard-read', 'clipboard-write'] });

test.describe('Helpdesk specialist investigates an access denial', () => {
  test('diagnoses the denial, shows the verified runbook and copies it', async ({ page }) => {
    const copilot = new CopilotConsolePage(page);
    await copilot.open();

    await copilot.ask('Student Alex was denied model deepseek-coder. Diagnose and provide runbook.');

    await expect(copilot.badge).toHaveText('Verified via Policy Engine [RULE-CAT-04]');
    await expect(copilot.runbookCard).toBeVisible();
    await expect(copilot.runbookSteps).toHaveText(runbook.steps);

    await copilot.copyRunbook.click();
    await expect(copilot.copySuccess).toBeVisible();

    const rendered = await copilot.runbookSteps.allTextContents();
    expect(await copilot.clipboardText()).toBe(rendered.join('\n'));
  });

  test('shows a visible error and no runbook when the inquiry names an unknown student', async ({
    page,
  }) => {
    const copilot = new CopilotConsolePage(page);
    await copilot.open();

    await copilot.ask('Student Zed was denied model deepseek-coder. Diagnose and provide runbook.');

    // Wait for the error first, so the absence checks below cannot pass before the answer arrives.
    await expect(copilot.errorState).toContainText('Entity Not Found in State: user#Zed.');
    await expect(copilot.badge).toHaveCount(0);
    await expect(copilot.runbookCard).toHaveCount(0);
    await expect(copilot.copyRunbook).toHaveCount(0);
  });
});
