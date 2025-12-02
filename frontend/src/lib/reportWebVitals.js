/**
 * Web Vitals Reporting
 * Tracks Core Web Vitals metrics:
 * - LCP (Largest Contentful Paint) - Loading performance
 * - INP (Interaction to Next Paint) - Responsiveness (replaces FID)
 * - CLS (Cumulative Layout Shift) - Visual stability
 * - FCP (First Contentful Paint) - Initial render
 * - TTFB (Time to First Byte) - Server response
 */

const reportWebVitals = (onPerfEntry) => {
  if (onPerfEntry && typeof onPerfEntry === 'function') {
    import('web-vitals').then(({ onCLS, onINP, onFCP, onLCP, onTTFB }) => {
      onCLS(onPerfEntry);
      onINP(onPerfEntry);
      onFCP(onPerfEntry);
      onLCP(onPerfEntry);
      onTTFB(onPerfEntry);
    });
  }
};

/**
 * Send metrics to analytics endpoint
 * @param {Object} metric - Web Vitals metric object
 */
export const sendToAnalytics = (metric) => {
  // Log to console in development only
  // Production analytics endpoint not implemented - metrics logged locally only
  if (import.meta.env.DEV) {
    const { name, value, rating } = metric;
    console.log(`[Web Vitals] ${name}: ${Math.round(value)} (${rating})`);
  }

  // Note: To enable production analytics, implement /api/analytics/vitals endpoint
  // and uncomment the code below:
  /*
  if (import.meta.env.PROD) {
    const body = JSON.stringify({
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      delta: metric.delta,
      id: metric.id,
      navigationType: metric.navigationType,
      timestamp: Date.now()
    });
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/analytics/vitals', body);
    }
  }
  */
};

export default reportWebVitals;
