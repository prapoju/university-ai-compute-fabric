// The only module that calls the API. Response bodies are untrusted: they are narrowed with type guards, never cast.

export interface Evidence {
  citation_id: string;
  source_type: string;
  snippet: string;
  position: number;
}

export interface Runbook {
  steps: string[];
  required_tools: string[];
  safety_warnings: string[];
  provenance: { source: string | null; version: string };
}

export interface Claim {
  claim_id: string;
  text: string;
}

export interface Answer {
  answer_id: string;
  intent: string;
  answer_chain: string[];
  diagnosis_class: string | null;
  canonical: string | null;
  claims: Claim[];
  evidence: Evidence[];
  recommendation: { runbook: Runbook } | null;
  prose: string;
}

export interface ErrorBody {
  code: string;
  status: number;
  message: string;
  retryable: boolean;
}

export interface AnswerEnvelope {
  answers: Answer[];
}

export type QueryResult = { kind: 'answers'; answers: Answer[] } | { kind: 'error'; message: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isErrorBody(value: unknown): value is ErrorBody {
  return isRecord(value) && typeof value.code === 'string' && typeof value.message === 'string';
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function isRunbook(value: unknown): value is Runbook {
  return (
    isRecord(value) &&
    isStringArray(value.steps) &&
    isStringArray(value.required_tools) &&
    isStringArray(value.safety_warnings) &&
    isRecord(value.provenance) &&
    typeof value.provenance.version === 'string'
  );
}

function isEvidence(value: unknown): value is Evidence {
  return (
    isRecord(value) &&
    typeof value.citation_id === 'string' &&
    typeof value.source_type === 'string' &&
    typeof value.snippet === 'string' &&
    typeof value.position === 'number'
  );
}

function isClaim(value: unknown): value is Claim {
  return isRecord(value) && typeof value.claim_id === 'string' && typeof value.text === 'string';
}

function isAnswer(value: unknown): value is Answer {
  if (!isRecord(value) || typeof value.answer_id !== 'string' || typeof value.prose !== 'string') {
    return false;
  }
  if (!Array.isArray(value.claims) || !value.claims.every(isClaim)) {
    return false;
  }
  if (!Array.isArray(value.evidence) || !value.evidence.every(isEvidence)) {
    return false;
  }
  if (value.recommendation === null) {
    return true;
  }
  return isRecord(value.recommendation) && isRunbook(value.recommendation.runbook);
}

function isAnswerEnvelope(value: unknown): value is AnswerEnvelope {
  return isRecord(value) && Array.isArray(value.answers) && value.answers.every(isAnswer);
}

// POST /api/v1/copilot/query. Synchronous: the promise resolves when the whole answer has arrived (no stream: impl2-rules, Streaming output).
export async function askCopilot(query: string): Promise<QueryResult> {
  let response: Response;
  try {
    response = await fetch('/api/v1/copilot/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
  } catch {
    return { kind: 'error', message: 'The copilot did not answer. Try again.' };
  }

  const body: unknown = await response.json().catch(() => null);
  if (isErrorBody(body)) {
    return { kind: 'error', message: body.message };
  }
  if (response.ok && isAnswerEnvelope(body)) {
    return { kind: 'answers', answers: body.answers };
  }
  return { kind: 'error', message: 'The copilot returned an answer this console cannot show.' };
}
