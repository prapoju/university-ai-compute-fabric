import { useState, type FormEvent } from 'react';

import { askCopilot, type Answer, type Runbook } from './api';
import { ruleOfClause } from './ruleOfClause';

type ViewState =
  | { kind: 'idle' }
  | { kind: 'pending' }
  | { kind: 'answered'; answers: Answer[] }
  | { kind: 'error'; message: string };

// UX-DR4: the composer caps the inquiry at 1,000 characters.
const MAX_INQUIRY_LENGTH = 1000;

// The badge text names the rule of the first policy clause whose evidence prints one (AD-2, AD-8: cited evidence only).
function policyBadge(answer: Answer): string | null {
  for (const item of answer.evidence) {
    if (item.source_type !== 'policy') {
      continue;
    }
    const rule = ruleOfClause(item.snippet, item.citation_id);
    if (rule !== null) {
      return `Verified via Policy Engine [${rule}]`;
    }
  }
  return null;
}

export function CopilotConsole() {
  const [inquiry, setInquiry] = useState('');
  const [view, setView] = useState<ViewState>({ kind: 'idle' });
  const pending = view.kind === 'pending';

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = inquiry.trim();
    if (query === '' || pending) {
      return;
    }
    setView({ kind: 'pending' });
    const result = await askCopilot(query);
    setView(
      result.kind === 'answers'
        ? { kind: 'answered', answers: result.answers }
        : { kind: 'error', message: result.message },
    );
  }

  return (
    <main className="page">
      <h1>Helpdesk copilot</h1>
      <form className="composer" onSubmit={submit}>
        <label htmlFor="inquiry">Inquiry</label>
        <textarea
          id="inquiry"
          rows={3}
          maxLength={MAX_INQUIRY_LENGTH}
          value={inquiry}
          onChange={(event) => setInquiry(event.target.value)}
        />
        <button type="submit" disabled={pending || inquiry.trim() === ''}>
          Submit Inquiry
        </button>
      </form>

      {pending && (
        <p role="status" data-testid="pending-state">
          Waiting for the answer…
        </p>
      )}
      {view.kind === 'error' && <div role="alert" className="error">{view.message}</div>}
      {view.kind === 'answered' && (
        <div data-testid="response">
          {view.answers.map((answer) => (
            <AnswerView key={answer.answer_id} answer={answer} />
          ))}
        </div>
      )}
    </main>
  );
}

function AnswerView({ answer }: { answer: Answer }) {
  const badge = policyBadge(answer);
  const runbook = answer.recommendation?.runbook ?? null;

  return (
    <article className="answer">
      {badge !== null && (
        <p className="badge" data-testid="citation-badge">
          {badge}
        </p>
      )}
      <p>{answer.prose}</p>
      <ul className="claims">
        {answer.claims.map((claim) => (
          <li key={claim.claim_id}>{claim.text}</li>
        ))}
      </ul>
      {runbook !== null && <RunbookCard runbook={runbook} />}
    </article>
  );
}

function RunbookCard({ runbook }: { runbook: Runbook }) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(runbook.steps.join('\n'));
      setCopied(true);
      setCopyFailed(false);
    } catch {
      setCopied(false);
      setCopyFailed(true);
    }
  }

  return (
    <section className="runbook" data-testid="runbook-card" aria-label="Troubleshooting runbook">
      <h2>Troubleshooting runbook</h2>
      <ol data-testid="runbook-steps">
        {runbook.steps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ol>
      {runbook.safety_warnings.length > 0 && (
        <ul className="warnings">
          {runbook.safety_warnings.map((warning, index) => (
            <li key={index}>{warning}</li>
          ))}
        </ul>
      )}
      <p className="provenance">
        Source: {runbook.provenance.source ?? 'unsourced'} · version {runbook.provenance.version}
      </p>
      <div className="runbook-actions">
        <button type="button" onClick={copyToClipboard}>
          Copy Runbook to Clipboard
        </button>
        {copied && (
          <span className="copy-success" data-testid="copy-success">
            ✓ Copied
          </span>
        )}
        {copyFailed && <span role="alert">Copy failed: the clipboard is not available.</span>}
      </div>
    </section>
  );
}
