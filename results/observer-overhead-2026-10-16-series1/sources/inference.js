import http from 'k6/http';
import { Rate, Trend } from 'k6/metrics';

const requestLatency = new Trend('request_latency_ms', true);
const successfulLatency = new Trend('successful_latency_ms', true);
const inferenceErrors = new Rate('inference_errors');
const outputTokens = new Trend('output_tokens');
const modelLoad = new Trend('model_load_ms', true);
const baseUrl = __ENV.BASE_URL;
if (!baseUrl) throw new Error('BASE_URL is required');

const low = Number(__ENV.LOW_RATE || 2);
const peak = Number(__ENV.RATE || 10);
const common = { timeUnit: '10s', preAllocatedVUs: 50, maxVUs: 100, gracefulStop: '35s' };
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

const payload = JSON.stringify({
  model: 'qwen2.5:0.5b',
  prompt: 'Explain what a container is in three short sentences.',
  stream: false,
  keep_alive: -1,
  options: { num_predict: 64, num_ctx: 1024, num_thread: 2, temperature: 0, seed: 42 },
});

export default function () {
  const started = Date.now();
  const response = http.post(`${baseUrl}/api/generate`, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  });
  const elapsed = Date.now() - started;
  requestLatency.add(elapsed);
  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }
  const ok = response.status === 200 && body && body.done === true && typeof body.response === 'string' && body.response.trim().length > 0;
  inferenceErrors.add(!ok);
  if (ok) {
    successfulLatency.add(elapsed);
    outputTokens.add(body.eval_count || 0);
    modelLoad.add((body.load_duration || 0) / 1e6);
  }
}
