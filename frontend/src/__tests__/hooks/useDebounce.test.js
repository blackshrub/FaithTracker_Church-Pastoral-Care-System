/**
 * Tests for useDebounce custom hook
 *
 * Critical for preventing excessive API calls during user input
 */

import { describe, expect, beforeEach, afterEach, test } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useDebounce } from '../../hooks/useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  test('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('initial', 300));
    expect(result.current).toBe('initial');
  });

  test('debounces value changes', () => {
    const { result, rerender } = renderHook(({ value, delay }) => useDebounce(value, delay), {
      initialProps: { value: 'initial', delay: 300 },
    });

    expect(result.current).toBe('initial');

    // Change value
    rerender({ value: 'updated', delay: 300 });

    // Should still be old value (not debounced yet)
    expect(result.current).toBe('initial');

    // Fast-forward time
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Now should be updated
    expect(result.current).toBe('updated');
  });

  test('cancels previous timeout on rapid changes', () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
      initialProps: { value: 'first' },
    });

    // Rapid changes
    rerender({ value: 'second' });
    act(() => vi.advanceTimersByTime(100));

    rerender({ value: 'third' });
    act(() => vi.advanceTimersByTime(100));

    rerender({ value: 'fourth' });

    // Should still be initial value
    expect(result.current).toBe('first');

    // Complete the debounce
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Should be the last value only
    expect(result.current).toBe('fourth');
  });

  test('respects custom delay', () => {
    const { result, rerender } = renderHook(({ value, delay }) => useDebounce(value, delay), {
      initialProps: { value: 'initial', delay: 500 },
    });

    rerender({ value: 'updated', delay: 500 });

    // After 300ms, should still be old value
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe('initial');

    // After full 500ms, should be updated
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe('updated');
  });

  test('uses default delay when not specified', () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value), {
      initialProps: { value: 'initial' },
    });

    rerender({ value: 'updated' });

    // Default is 300ms
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe('updated');
  });

  test('handles empty string values', () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
      initialProps: { value: '' },
    });

    expect(result.current).toBe('');

    rerender({ value: 'text' });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe('text');
  });

  test('handles number values', () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
      initialProps: { value: 0 },
    });

    expect(result.current).toBe(0);

    rerender({ value: 42 });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe(42);
  });
});
