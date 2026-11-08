import type { Locator, Page } from '@playwright/test';

// Page object for the Copilot console at /helpdesk/copilot (story 1.7, Annex 12.6).
// Every selector and every user action of the console lives here. Specs assert; this class never does.
// The console (console/src) implements exactly these roles and test ids; changing one means changing both.

export class CopilotConsolePage {
  readonly prompt: Locator;
  readonly submit: Locator;
  readonly pending: Locator;
  readonly response: Locator;
  readonly badge: Locator;
  readonly runbookCard: Locator;
  readonly runbookSteps: Locator;
  readonly copyRunbook: Locator;
  readonly copySuccess: Locator;
  readonly errorState: Locator;

  constructor(private readonly page: Page) {
    this.prompt = page.getByRole('textbox', { name: 'Inquiry' });
    this.submit = page.getByRole('button', { name: 'Submit Inquiry' });
    this.pending = page.getByTestId('pending-state');
    this.response = page.getByTestId('response');
    this.badge = page.getByTestId('citation-badge');
    this.runbookCard = page.getByTestId('runbook-card');
    this.runbookSteps = page.getByTestId('runbook-steps').getByRole('listitem');
    this.copyRunbook = page.getByRole('button', { name: 'Copy Runbook to Clipboard' });
    this.copySuccess = page.getByTestId('copy-success');
    this.errorState = page.getByRole('alert');
  }

  async open(): Promise<void> {
    await this.page.goto('/helpdesk/copilot');
  }

  async ask(inquiry: string): Promise<void> {
    await this.prompt.fill(inquiry);
    await this.submit.click();
  }

  async clipboardText(): Promise<string> {
    return this.page.evaluate(() => navigator.clipboard.readText());
  }
}
