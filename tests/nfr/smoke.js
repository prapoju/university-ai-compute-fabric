// k6 smoke: the liveness probe holds a small steady load.
// Run: k6 run tests/nfr/smoke.js   (BASE_URL defaults to http://127.0.0.1:8000; see `make nfr`)
//
// No fixed pauses: the constant-arrival-rate executor paces the load (docs/impl2-rules.md).
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export const options = {
  scenarios: {
    healthz: {
      executor: 'constant-arrival-rate',
      rate: 20,
      timeUnit: '1s',
      duration: '10s',
      preAllocatedVUs: 5,
      maxVUs: 10,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<200'],
    checks: ['rate==1'],
    dropped_iterations: ['count==0'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/healthz`);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body is ok': (r) => r.json('status') === 'ok',
  });
}
