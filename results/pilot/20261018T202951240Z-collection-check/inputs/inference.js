import http from 'k6/http';
import exec from 'k6/execution';
import { Counter, Rate, Trend } from 'k6/metrics';

const workload = JSON.parse(open('./workload.json'));
const requestsStarted = new Counter('requests_started');
const requestsCompleted = new Counter('requests_completed');

const requestLatency = new Trend('request_latency_ms', true);
const successfulLatency = new Trend('successful_latency_ms', true);
const inferenceErrors = new Rate('inference_errors');
const outputTokens = new Trend('output_tokens');
const modelLoad = new Trend('model_load_ms', true);
const outputTokensAvailable = new Rate('output_tokens_available');
const modelLoadAvailable = new Rate('model_load_available');
const baseUrl = __ENV.BASE_URL;
if (!baseUrl) throw new Error('BASE_URL is required');

const low = Number(__ENV.LOW_RATE || 2);
const peak = Number(__ENV.RATE || 10);
const common = {
  timeUnit: `${workload.time_unit_seconds}s`, preAllocatedVUs: workload.preallocated_vus,
  maxVUs: workload.max_vus, gracefulStop: `${workload.graceful_stop_seconds}s`,
};
const load = __ENV.PROFILE === 'burst'
  ? {
      ...common,
      executor: 'ramping-arrival-rate',
      startRate: low,
      stages: [
        { duration: '2m', target: low },
        { duration: '1s', target: peak },
        { duration: '5m', target: peak },
        { duration: '1s', target: low },
        { duration: '6m', target: low },
      ],
    }
  : { ...common, executor: 'constant-arrival-rate', rate: peak, duration: __ENV.DURATION || '13m2s' };

export const options = {
  scenarios: { load },
  noConnectionReuse: true,
  thresholds: {
    dropped_iterations: ['count==0'],
    inference_errors: ['rate<=0.01'],
    ...(__ENV.SLO_MS ? { successful_latency_ms: [`p(95)<=${Number(__ENV.SLO_MS)}`] } : {}),
  },
};

const payload = JSON.stringify(workload.request);

function emit(event) {
  if (__ENV.REQUEST_EVENTS === '1') console.log(JSON.stringify(event));
}

export default function () {
  const started = Date.now();
  const identity = {
    schema_version: 1, run_id: __ENV.RUN_ID || 'standalone', phase: 'load',
    request_id: `${__ENV.RUN_ID || 'standalone'}:${exec.scenario.name}:${exec.scenario.iterationInTest}`,
    scenario: exec.scenario.name, iteration: exec.scenario.iterationInTest, vu: exec.vu.idInTest,
    scenario_started_at_utc: new Date(exec.scenario.startTime).toISOString(),
    started_at_utc: new Date(started).toISOString(),
  };
  emit({ ...identity, event: 'started' });
  requestsStarted.add(1);
  const response = http.post(`${baseUrl}/api/generate`, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: `${workload.timeout_seconds}s`, redirects: 0,
  });
  const finished = Date.now();
  const elapsed = finished - started;
  requestLatency.add(elapsed);
  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }
  const ok = Boolean(response.status === 200 && body && body.done === true && typeof body.response === 'string' && body.response.trim().length > 0);
  const hasTokens = ok && Number.isSafeInteger(body.eval_count) && body.eval_count >= 0;
  const hasLoadDuration = ok && Number.isSafeInteger(body.load_duration) && body.load_duration >= 0;
  let errorCategory = null;
  if (response.error_code === 1050) errorCategory = 'timeout';
  else if (response.status === 0) errorCategory = 'transport';
  else if (response.status !== 200) errorCategory = 'http_status';
  else if (body === null) errorCategory = 'invalid_json';
  else if (body.done !== true) errorCategory = 'incomplete_response';
  else if (!ok) errorCategory = 'empty_response';
  emit({
    ...identity, event: 'completed', finished_at_utc: new Date(finished).toISOString(),
    duration_ms: elapsed, http_duration_ms: response.timings.duration,
    http_status: response.status, outcome: ok ? 'success' : 'failure',
    error_category: errorCategory, error_code: response.error_code || null,
    output_tokens: hasTokens ? body.eval_count : null,
    model_load_ms: hasLoadDuration ? body.load_duration / 1e6 : null,
  });
  requestsCompleted.add(1);
  inferenceErrors.add(!ok);
  if (ok) {
    successfulLatency.add(elapsed);
    outputTokensAvailable.add(hasTokens);
    modelLoadAvailable.add(hasLoadDuration);
    if (hasTokens) outputTokens.add(body.eval_count);
    if (hasLoadDuration) modelLoad.add(body.load_duration / 1e6);
  }
}
