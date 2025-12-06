import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";
import App from "@/App";
import reportWebVitals, { sendToAnalytics } from "@/lib/reportWebVitals";

// Comprehensive ResizeObserver error suppression
// Method 1: Window error event
window.addEventListener('error', (e) => {
  if (e.message && e.message.includes('ResizeObserver loop')) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
  // Handle chunk load errors (after new deployments)
  if (
    e.message?.includes('Failed to fetch dynamically imported module') ||
    e.message?.includes('Loading chunk') ||
    e.message?.includes('Loading CSS chunk')
  ) {
    e.preventDefault();
    const hasReloaded = sessionStorage.getItem('chunk_reload_attempted');
    if (!hasReloaded) {
      sessionStorage.setItem('chunk_reload_attempted', 'true');
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations().then((regs) => {
          regs.forEach((reg) => reg.unregister());
        });
      }
      if ('caches' in window) {
        caches.keys().then((names) => names.forEach((n) => caches.delete(n)));
      }
      window.location.reload(true);
    }
    return false;
  }
});

// Method 2: Unhandled rejection
window.addEventListener('unhandledrejection', (e) => {
  if (e.reason && e.reason.message && e.reason.message.includes('ResizeObserver')) {
    e.stopImmediatePropagation();
    e.preventDefault();
    return false;
  }
  // Handle chunk load errors (after new deployments)
  if (
    e.reason?.message?.includes('Failed to fetch dynamically imported module') ||
    e.reason?.message?.includes('Loading chunk') ||
    e.reason?.message?.includes('Loading CSS chunk') ||
    e.reason?.name === 'ChunkLoadError'
  ) {
    e.preventDefault();
    const hasReloaded = sessionStorage.getItem('chunk_reload_attempted');
    if (!hasReloaded) {
      sessionStorage.setItem('chunk_reload_attempted', 'true');
      // Clear service worker and caches, then reload
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations().then((regs) => {
          regs.forEach((reg) => reg.unregister());
        });
      }
      if ('caches' in window) {
        caches.keys().then((names) => names.forEach((n) => caches.delete(n)));
      }
      window.location.reload(true);
    }
    return false;
  }
});

// Method 3: Override console.error temporarily
const originalError = console.error;
console.error = (...args) => {
  if (args[0] && typeof args[0] === 'string' && args[0].includes('ResizeObserver')) {
    return;
  }
  originalError.apply(console, args);
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Track Web Vitals for performance monitoring
reportWebVitals(sendToAnalytics);
