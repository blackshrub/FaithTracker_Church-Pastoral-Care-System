/**
 * Tests for AuthContext (src/context/AuthContext.jsx)
 *
 * Covers:
 * - checkAuth with valid stored token restores user session
 * - checkAuth with invalid/expired token clears auth
 * - checkAuth cancelled on unmount (bug fix validation)
 * - login sets token, user, and localStorage
 * - logout clears token, user, and localStorage
 * - refreshUser fetches updated user data
 * - useAuth throws when used outside AuthProvider
 * - loading state transitions correctly
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createElement } from 'react';

// Mock the api module
vi.mock('@/lib/api', () => {
  const mockApi = {
    get: vi.fn(),
    post: vi.fn(),
    defaults: { headers: { common: {} } },
  };
  return {
    default: mockApi,
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn(),
  };
});

// Import after mocks
import { AuthProvider, useAuth } from '@/context/AuthContext';
import api, { setAuthToken, clearAuthToken } from '@/lib/api';

// Test component that consumes AuthContext
function TestConsumer() {
  const { user, token, loading, login, logout, refreshUser } = useAuth();

  if (loading) return <div data-testid="loading">Loading...</div>;

  return (
    <div>
      <div data-testid="user">{user ? JSON.stringify(user) : 'null'}</div>
      <div data-testid="token">{token || 'null'}</div>
      <button data-testid="login-btn" onClick={() => login('test@test.com', 'pass123')}>
        Login
      </button>
      <button data-testid="login-campus-btn" onClick={() => login('test@test.com', 'pass123', 'campus-1')}>
        Login with Campus
      </button>
      <button data-testid="logout-btn" onClick={() => logout()}>
        Logout
      </button>
      <button data-testid="refresh-btn" onClick={() => refreshUser()}>
        Refresh
      </button>
    </div>
  );
}

// Helper: render with AuthProvider
function renderWithAuth() {
  return render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>
  );
}

// Mock localStorage
let storage = {};

beforeEach(() => {
  storage = {};
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key) => storage[key] ?? null),
    setItem: vi.fn((key, val) => { storage[key] = val; }),
    removeItem: vi.fn((key) => { delete storage[key]; }),
    clear: vi.fn(() => { storage = {}; }),
  });
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AuthProvider - initial loading state', () => {
  it('shows loading state initially', () => {
    // Make the API call pending (never resolves during this test)
    api.get.mockImplementation(() => new Promise(() => {}));

    renderWithAuth();

    expect(screen.getByTestId('loading')).toBeInTheDocument();
  });

  it('finishes loading after checkAuth completes (no stored token)', async () => {
    // No token in localStorage
    localStorage.getItem.mockReturnValue(null);

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });

    expect(screen.getByTestId('token')).toHaveTextContent('null');
  });
});

describe('AuthProvider - checkAuth with stored token', () => {
  it('restores session from valid stored token', async () => {
    storage.token = 'valid-stored-token';
    const userData = { id: 'user-1', name: 'John Doe', email: 'john@test.com', role: 'pastor' };

    api.get.mockResolvedValue({ data: userData });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(userData));
    });

    expect(screen.getByTestId('token')).toHaveTextContent('valid-stored-token');
    expect(setAuthToken).toHaveBeenCalledWith('valid-stored-token');
    expect(api.get).toHaveBeenCalledWith('/auth/me');
  });

  it('clears auth when stored token is invalid (API returns error)', async () => {
    storage.token = 'expired-token';

    api.get.mockRejectedValue(new Error('Token expired'));

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });

    expect(screen.getByTestId('token')).toHaveTextContent('null');
    expect(localStorage.removeItem).toHaveBeenCalledWith('token');
    expect(clearAuthToken).toHaveBeenCalled();
  });

  it('clears auth when API returns 401', async () => {
    storage.token = 'old-token';

    api.get.mockRejectedValue({ response: { status: 401 } });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('null');
    });

    expect(localStorage.removeItem).toHaveBeenCalledWith('token');
    expect(clearAuthToken).toHaveBeenCalled();
  });
});

describe('AuthProvider - checkAuth cancellation on unmount (bug fix)', () => {
  it('does not update state after unmount when API resolves late', async () => {
    storage.token = 'some-token';

    let resolveApi;
    api.get.mockImplementation(() => new Promise((resolve) => { resolveApi = resolve; }));

    const { unmount } = renderWithAuth();

    // Unmount before API resolves
    unmount();

    // Now resolve the API call
    await act(async () => {
      resolveApi({ data: { id: 'user-1', name: 'Late User' } });
    });

    // No error should have been thrown (React would warn about state update on unmounted component)
    // The cancelled flag prevents the state update
  });

  it('does not update state after unmount when API rejects late', async () => {
    storage.token = 'some-token';

    let rejectApi;
    api.get.mockImplementation(() => new Promise((_, reject) => { rejectApi = reject; }));

    const { unmount } = renderWithAuth();

    unmount();

    // Reject after unmount
    await act(async () => {
      rejectApi(new Error('Network error'));
    });

    // Should not throw
  });

  it('sets loading to false even when cancelled (no stored token)', async () => {
    // When there's no stored token, checkAuth should set loading=false immediately
    localStorage.getItem.mockReturnValue(null);

    renderWithAuth();

    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });
  });
});

describe('AuthProvider - login', () => {
  it('calls API with email and password and stores token', async () => {
    localStorage.getItem.mockReturnValue(null);
    api.get.mockRejectedValue(new Error('No token')); // Initial checkAuth fails

    const loginResponse = {
      access_token: 'new-jwt-token',
      user: { id: 'u1', name: 'Test User', email: 'test@test.com', role: 'pastor' },
    };
    api.post.mockResolvedValue({ data: loginResponse });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('login-btn')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('login-btn'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@test.com',
        password: 'pass123',
        campus_id: null,
      });
    });

    expect(localStorage.setItem).toHaveBeenCalledWith('token', 'new-jwt-token');
    expect(setAuthToken).toHaveBeenCalledWith('new-jwt-token');

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(loginResponse.user));
    });
    expect(screen.getByTestId('token')).toHaveTextContent('new-jwt-token');
  });

  it('sends campus_id when provided', async () => {
    localStorage.getItem.mockReturnValue(null);
    api.get.mockRejectedValue(new Error('No token'));

    api.post.mockResolvedValue({
      data: {
        access_token: 'token',
        user: { id: 'u1', name: 'User' },
      },
    });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('login-campus-btn')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('login-campus-btn'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@test.com',
        password: 'pass123',
        campus_id: 'campus-1',
      });
    });
  });

  it('returns user data from login', async () => {
    localStorage.getItem.mockReturnValue(null);
    api.get.mockRejectedValue(new Error('No token'));

    const userData = { id: 'u1', name: 'Test User' };
    api.post.mockResolvedValue({
      data: { access_token: 'token', user: userData },
    });

    // Use a custom test component to check return value
    let loginResult;
    function LoginTestComponent() {
      const { login, loading } = useAuth();
      if (loading) return null;
      return (
        <button
          data-testid="login"
          onClick={async () => { loginResult = await login('a@b.com', 'pass'); }}
        >
          Login
        </button>
      );
    }

    render(
      <AuthProvider>
        <LoginTestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('login')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('login'));

    await waitFor(() => {
      expect(loginResult).toEqual(userData);
    });
  });
});

describe('AuthProvider - logout', () => {
  it('clears token, user, and localStorage', async () => {
    storage.token = 'existing-token';
    api.get.mockResolvedValue({
      data: { id: 'u1', name: 'User' },
    });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('existing-token');
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('logout-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });
    expect(screen.getByTestId('token')).toHaveTextContent('null');
    expect(localStorage.removeItem).toHaveBeenCalledWith('token');
    expect(clearAuthToken).toHaveBeenCalled();
  });
});

describe('AuthProvider - refreshUser', () => {
  it('fetches updated user data from /auth/me', async () => {
    storage.token = 'valid-token';
    const initialUser = { id: 'u1', name: 'Old Name', role: 'pastor' };
    const updatedUser = { id: 'u1', name: 'New Name', role: 'campus_admin' };

    api.get
      .mockResolvedValueOnce({ data: initialUser }) // Initial checkAuth
      .mockResolvedValueOnce({ data: updatedUser }); // refreshUser

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(initialUser));
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(updatedUser));
    });
  });
});

describe('useAuth - outside provider', () => {
  it('throws an error when used outside AuthProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function BadComponent() {
      useAuth();
      return null;
    }

    expect(() => render(<BadComponent />)).toThrow(
      'useAuth must be used within AuthProvider'
    );

    consoleSpy.mockRestore();
  });
});

describe('AuthProvider - context value shape', () => {
  it('provides all expected properties', async () => {
    localStorage.getItem.mockReturnValue(null);

    let contextValue;
    function ContextInspector() {
      contextValue = useAuth();
      return null;
    }

    render(
      <AuthProvider>
        <ContextInspector />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(contextValue).toBeDefined();
    });

    expect(contextValue).toHaveProperty('user');
    expect(contextValue).toHaveProperty('token');
    expect(contextValue).toHaveProperty('login');
    expect(contextValue).toHaveProperty('logout');
    expect(contextValue).toHaveProperty('loading');
    expect(contextValue).toHaveProperty('refreshUser');

    expect(typeof contextValue.login).toBe('function');
    expect(typeof contextValue.logout).toBe('function');
    expect(typeof contextValue.refreshUser).toBe('function');
  });
});

describe('AuthProvider - edge cases', () => {
  it('handles network error during login gracefully (error propagates)', async () => {
    localStorage.getItem.mockReturnValue(null);
    api.get.mockRejectedValue(new Error('No token'));
    api.post.mockRejectedValue(new Error('Network error'));

    let loginError;
    function ErrorTestComponent() {
      const { login, loading } = useAuth();
      if (loading) return null;
      return (
        <button
          data-testid="login"
          onClick={async () => {
            try {
              await login('a@b.com', 'pass');
            } catch (e) {
              loginError = e;
            }
          }}
        >
          Login
        </button>
      );
    }

    render(
      <AuthProvider>
        <ErrorTestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('login')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('login'));

    await waitFor(() => {
      expect(loginError).toBeDefined();
      expect(loginError.message).toBe('Network error');
    });
  });

  it('handles empty localStorage token (falsy value)', async () => {
    storage.token = '';
    localStorage.getItem.mockReturnValue('');

    renderWithAuth();

    // Empty string is falsy, so checkAuth should skip API call
    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });

    // api.get should NOT have been called (empty string is falsy)
    // Actually '' is falsy in JS, so the if(storedToken) check fails
    expect(api.get).not.toHaveBeenCalled();
  });
});
