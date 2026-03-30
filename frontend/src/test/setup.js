/**
 * Vitest global test setup
 *
 * Provides:
 * - @testing-library/jest-dom matchers (toBeInTheDocument, etc.)
 * - fake-indexeddb for IndexedDB tests
 * - Common browser API mocks (localStorage, matchMedia, EventSource)
 */

import '@testing-library/jest-dom';

// Polyfill IndexedDB for jsdom (used by offlineQueue tests)
import 'fake-indexeddb/auto';

// Mock import.meta.env for Vite
// Vitest handles this natively, but ensure defaults are present
if (!import.meta.env.VITE_BACKEND_URL) {
  import.meta.env.VITE_BACKEND_URL = 'http://localhost:8001';
}

// Mock matchMedia (used by responsive components)
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// Mock IntersectionObserver (used by lazy loading / infinite scroll)
if (typeof window !== 'undefined' && !window.IntersectionObserver) {
  window.IntersectionObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));
}

// Mock ResizeObserver (used by Radix UI components)
if (typeof window !== 'undefined' && !window.ResizeObserver) {
  window.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));
}

// Suppress console.error for expected React warnings in tests
// (e.g., act() warnings from async state updates)
const originalConsoleError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    // Filter out known noisy warnings
    const msg = typeof args[0] === 'string' ? args[0] : '';
    if (msg.includes('Not implemented: navigation') || msg.includes('Error: Uncaught')) {
      return;
    }
    originalConsoleError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalConsoleError;
});
