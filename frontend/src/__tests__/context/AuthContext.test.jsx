/**
 * Tests for AuthContext (src/context/AuthContext.tsx)
 *
 * After the httpOnly-cookie migration, the context no longer exposes a `token`
 * and no longer reads/writes localStorage on login. Auth lives in the server
 * cookie; the context only tracks user state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

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

import { AuthProvider, useAuth } from '@/context/AuthContext';
import api from '@/lib/api';

function TestConsumer() {
  const { user, loading, login, logout, refreshUser } = useAuth();
  if (loading) return <div data-testid="loading">Loading...</div>;
  return (
    <div>
      <div data-testid="user">{user ? JSON.stringify(user) : 'null'}</div>
      <button data-testid="login-btn" onClick={() => login('test@test.com', 'pass123')}>
        Login
      </button>
      <button
        data-testid="login-campus-btn"
        onClick={() => login('test@test.com', 'pass123', 'campus-1')}
      >
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

function renderWithAuth() {
  return render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>
  );
}

let storage = {};

beforeEach(() => {
  storage = {};
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key) => storage[key] ?? null),
    setItem: vi.fn((key, val) => {
      storage[key] = val;
    }),
    removeItem: vi.fn((key) => {
      delete storage[key];
    }),
    clear: vi.fn(() => {
      storage = {};
    }),
  });
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AuthProvider - initial loading state', () => {
  it('shows loading while probing /auth/me', () => {
    api.get.mockImplementation(() => new Promise(() => {}));
    renderWithAuth();
    expect(screen.getByTestId('loading')).toBeInTheDocument();
  });

  it('renders unauthenticated state when /auth/me rejects', async () => {
    api.get.mockRejectedValue({ response: { status: 401 } });
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });
    expect(api.get).toHaveBeenCalledWith('/auth/me');
  });
});

describe('AuthProvider - checkAuth via cookie', () => {
  it('restores session from valid auth cookie (server returns user on /auth/me)', async () => {
    const userData = { id: 'user-1', name: 'John Doe', email: 'john@test.com', role: 'pastor' };
    api.get.mockResolvedValue({ data: userData });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(userData));
    });
    expect(api.get).toHaveBeenCalledWith('/auth/me');
  });

  it('clears any legacy localStorage token on mount', async () => {
    storage.token = 'legacy-token';
    api.get.mockRejectedValue({ response: { status: 401 } });

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });
    expect(localStorage.removeItem).toHaveBeenCalledWith('token');
  });
});

describe('AuthProvider - checkAuth cancellation on unmount', () => {
  it('does not throw when API resolves after unmount', async () => {
    let resolveApi;
    api.get.mockImplementation(() => new Promise((resolve) => (resolveApi = resolve)));
    const { unmount } = renderWithAuth();
    unmount();
    await act(async () => {
      resolveApi({ data: { id: 'user-1', name: 'Late' } });
    });
  });

  it('does not throw when API rejects after unmount', async () => {
    let rejectApi;
    api.get.mockImplementation(() => new Promise((_, reject) => (rejectApi = reject)));
    const { unmount } = renderWithAuth();
    unmount();
    await act(async () => {
      rejectApi(new Error('Network error'));
    });
  });
});

describe('AuthProvider - login', () => {
  it('calls /auth/login with credentials and sets user from response body', async () => {
    api.get.mockRejectedValue({ response: { status: 401 } });
    const userData = { id: 'u1', name: 'Test', email: 'test@test.com', role: 'pastor' };
    api.post.mockResolvedValue({ data: { access_token: 'ignored', user: userData } });

    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('login-btn')).toBeInTheDocument());

    await userEvent.setup().click(screen.getByTestId('login-btn'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@test.com',
        password: 'pass123',
        campus_id: null,
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(userData));
    });
    // Must not persist token to localStorage (cookie is the source of truth now).
    expect(localStorage.setItem).not.toHaveBeenCalledWith('token', expect.anything());
  });

  it('sends campus_id when provided', async () => {
    api.get.mockRejectedValue({ response: { status: 401 } });
    api.post.mockResolvedValue({ data: { access_token: 't', user: { id: 'u1', name: 'U' } } });

    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('login-campus-btn')).toBeInTheDocument());

    await userEvent.setup().click(screen.getByTestId('login-campus-btn'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@test.com',
        password: 'pass123',
        campus_id: 'campus-1',
      });
    });
  });

  it('returns the user from login()', async () => {
    api.get.mockRejectedValue({ response: { status: 401 } });
    const userData = { id: 'u1', name: 'Test' };
    api.post.mockResolvedValue({ data: { access_token: 't', user: userData } });

    let loginResult;
    function LoginTestComponent() {
      const { login, loading } = useAuth();
      if (loading) return null;
      return (
        <button
          data-testid="login"
          onClick={async () => {
            loginResult = await login('a@b.com', 'pass');
          }}
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
    await waitFor(() => expect(screen.getByTestId('login')).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId('login'));
    await waitFor(() => expect(loginResult).toEqual(userData));
  });
});

describe('AuthProvider - logout', () => {
  it('POSTs /auth/logout and clears user state', async () => {
    api.get.mockResolvedValue({ data: { id: 'u1', name: 'User' } });
    api.post.mockResolvedValue({ data: { success: true } });

    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('User');
    });

    await userEvent.setup().click(screen.getByTestId('logout-btn'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/logout');
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });
  });

  it('still clears user state even if /auth/logout fails', async () => {
    api.get.mockResolvedValue({ data: { id: 'u1', name: 'User' } });
    api.post.mockRejectedValue(new Error('offline'));

    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('User');
    });

    await userEvent.setup().click(screen.getByTestId('logout-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });
  });
});

describe('AuthProvider - refreshUser', () => {
  it('fetches updated user from /auth/me', async () => {
    const initial = { id: 'u1', name: 'Old', role: 'pastor' };
    const updated = { id: 'u1', name: 'New', role: 'campus_admin' };
    api.get.mockResolvedValueOnce({ data: initial }).mockResolvedValueOnce({ data: updated });

    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(initial));
    });

    await userEvent.setup().click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent(JSON.stringify(updated));
    });
  });
});

describe('useAuth - outside provider', () => {
  it('throws when used outside AuthProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    function BadComponent() {
      useAuth();
      return null;
    }
    expect(() => render(<BadComponent />)).toThrow('useAuth must be used within AuthProvider');
    consoleSpy.mockRestore();
  });
});

describe('AuthProvider - edge cases', () => {
  it('propagates network errors from login', async () => {
    api.get.mockRejectedValue({ response: { status: 401 } });
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
    await waitFor(() => expect(screen.getByTestId('login')).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId('login'));
    await waitFor(() => {
      expect(loginError).toBeDefined();
      expect(loginError.message).toBe('Network error');
    });
  });
});
