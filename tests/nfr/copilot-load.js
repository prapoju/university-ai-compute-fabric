// k6 load for story 1.6 (Annex 12.5): 50 operators, the literal S1 query, one request per iteration.
// Run: BASE_URL=http://127.0.0.1:8000 k6 run --summary-export=docs/evidence/impl2/k6-12-5.json tests/nfr/copilot-load.js
//
// No sleep calls: the per-vu-iterations executor is the load shape (docs/impl2-rules.md).
// The thresholds are the story's acceptance gate and are never relaxed (log I2-35).
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const QUERY = 'Why was student Alex denied access to model deepseek-coder?';

export const options = {
  scenarios: {
    operators: {
      executor: 'per-vu-iterations',
      vus: 50,
      iterations: 20,
      maxDuration: '10m',
    },
  },
  thresholds: {
    http_req_failed: ['rate==0'],
    http_req_duration: ['p(95)<800'],
    checks: ['rate==1'],
  },
};

export default function () {
  const res = http.post(
    `${BASE_URL}/api/v1/copilot/query`,
    JSON.stringify({ query: QUERY }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  const body = res.body || '';
  check(res, {
    'status is 200': (r) => r.status === 200,
    'cites RULE-CAT-04': () => body.includes('RULE-CAT-04'),
    'cites policy#catalog.4.2': () => body.includes('policy#catalog.4.2'),
    'cites deepseek-coder': () => body.includes('deepseek-coder'),
  });
}
