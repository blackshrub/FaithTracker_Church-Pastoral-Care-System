/**
 * Sentry/GlitchTip wiring for FaithTracker web (pastoral care dashboard).
 *
 * Initialize early in main.jsx before React renders so the SDK captures
 * errors from the initial mount. Self-hosted at errors.gkbj.org/3.
 */

import * as Sentry from '@sentry/react';

const DSN =
  import.meta.env.VITE_SENTRY_DSN || 'https://6d5c13f4082a4839aeb8e2448d373bf3@errors.gkbj.org/3';

const SENSITIVE_KEY_RE =
  /^(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)$/i;

function redact(value, seen = new WeakSet()) {
  if (!value || typeof value !== 'object') return value;
  if (seen.has(value)) return value;
  seen.add(value);
  if (Array.isArray(value)) return value.map((v) => redact(v, seen));
  if (Object.getPrototypeOf(value) === Object.prototype) {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = SENSITIVE_KEY_RE.test(k) ? '[redacted]' : redact(v, seen);
    }
    return out;
  }
  return value;
}

let initialized = false;

export function initSentry() {
  if (initialized || !DSN) return;
  Sentry.init({
    dsn: DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.05,
    replaysOnErrorSampleRate: 0.1,
    integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
    beforeSend(event) {
      if (
        event.exception?.values?.some(
          (v) => v.value && /network|timeout|aborted|failed to fetch|chunk load/i.test(v.value)
        )
      ) {
        return null;
      }
      return redact(event);
    },
    beforeBreadcrumb(crumb) {
      if (crumb.data && typeof crumb.data === 'object') {
        crumb.data = redact(crumb.data);
      }
      return crumb;
    },
  });
  initialized = true;
}

export { Sentry };
