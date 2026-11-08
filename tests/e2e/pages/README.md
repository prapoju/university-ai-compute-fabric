# Page objects

One class per console page (`<name>.page.ts`). Each takes the Playwright `Page` in its
constructor, exposes locators by role or `data-testid`, and exposes intent-level actions
(`ask(question)`, `confirm(token)`). Page objects never assert: specs do, with web-first
assertions (`await expect(locator).toBeVisible()`). No `waitForTimeout`.

The Copilot console page object lives in `CopilotConsolePage.ts` (story 1-7).
