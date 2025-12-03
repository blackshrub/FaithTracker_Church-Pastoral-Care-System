/**
 * App.jsx - Root React component and routing
 * Sets up React Query, authentication context, and application routes
 *
 * Performance optimizations:
 * - Lazy loading for all pages
 * - React Compiler enabled for automatic memoization
 * - TanStack Query handles caching (staleTime/gcTime for fast navigation)
 */

import React, { Suspense, lazy, useState, useEffect } from 'react';
import {
  createBrowserRouter,
  RouterProvider,
  Navigate,
  Outlet,
  useRouteError,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import PageLoader from '@/components/PageLoader';
import './i18n';
import '@/App.css';
import LoginPage from '@/pages/LoginPage';
import api from '@/lib/api';

// Create query client with optimized defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // Data considered fresh for 30 seconds
      gcTime: 1000 * 60 * 5, // Keep unused data in cache for 5 minutes
      refetchOnWindowFocus: true, // Refetch when user returns to tab
      retry: 1, // Retry failed requests once
    },
    mutations: {
      retry: 1,
    },
  },
});


// Lazy load components for code splitting
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const MembersList = lazy(() => import('@/pages/MembersList'));
const MemberDetail = lazy(() => import('@/pages/MemberDetail'));
const FinancialAid = lazy(() => import('@/pages/FinancialAid'));
const Analytics = lazy(() => import('@/pages/Analytics'));
const Reports = lazy(() => import('@/pages/Reports'));
const AdminDashboard = lazy(() => import('@/pages/AdminDashboard'));
const ImportExport = lazy(() => import('@/pages/ImportExport'));
const Settings = lazy(() => import('@/pages/Settings'));
const WhatsAppLogs = lazy(() => import('@/pages/WhatsAppLogs'));
const Calendar = lazy(() => import('@/pages/Calendar'));
const BulkMessaging = lazy(() => import('@/pages/BulkMessaging'));
const Reminders = lazy(() => import('@/pages/Reminders'));
const ActivityLog = lazy(() => import('@/pages/ActivityLog'));
const SetupWizard = lazy(() => import('@/pages/SetupWizard'));
const IntegrationTest = lazy(() => import('@/components/IntegrationTest'));
const Layout = lazy(() => import('@/components/Layout'));

// Protected route wrapper component
const ProtectedRoute = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return <PageLoader />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Layout>
      <Suspense fallback={<PageLoader />}>
        <Outlet />
      </Suspense>
    </Layout>
  );
};

// Auth-aware login route
const LoginRoute = () => {
  const { user } = useAuth();
  return user ? <Navigate to="/dashboard" replace /> : <LoginPage />;
};

// Root component that handles setup check
const RootLayout = () => {
  const [needsSetup, setNeedsSetup] = useState(null);

  useEffect(() => {
    const checkSetup = async () => {
      try {
        const response = await api.get('/setup/status');
        setNeedsSetup(response.data.needs_setup);
      } catch (error) {
        console.error('Error checking setup status:', error);
        setNeedsSetup(false);
      }
    };
    checkSetup();
  }, []);

  if (needsSetup === null) {
    return <PageLoader />;
  }

  if (needsSetup) {
    return (
      <Suspense fallback={<PageLoader />}>
        <SetupWizard onComplete={() => setNeedsSetup(false)} />
      </Suspense>
    );
  }

  return (
    <>
      <Outlet />
      <Toaster />
    </>
  );
};

// Error element for route errors
const RouteError = () => {
  const error = useRouteError();
  console.error('Route error:', error);
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Page Error</h1>
        <p className="text-gray-600 mb-4">{error?.message || 'Something went wrong'}</p>
        <a href="/dashboard" className="text-teal-600 hover:underline">Go to Dashboard</a>
      </div>
    </div>
  );
};

// Create router with data loaders for parallel data fetching
const router = createBrowserRouter([
  {
    element: <RootLayout />,
    // HydrateFallback for client-side only apps (prevents console warning)
    HydrateFallback: PageLoader,
    errorElement: <RouteError />,
    children: [
      {
        path: '/login',
        element: <LoginRoute />,
      },
      {
        element: <ProtectedRoute />,
        errorElement: <RouteError />,
        children: [
          {
            path: '/',
            element: <Dashboard />,
          },
          {
            path: '/dashboard',
            element: <Dashboard />,
          },
          {
            path: '/members',
            element: <MembersList />,
          },
          {
            path: '/members/:id',
            element: <MemberDetail />,
          },
          {
            path: '/financial-aid',
            element: <FinancialAid />,
          },
          {
            path: '/analytics',
            element: <Analytics />,
          },
          {
            path: '/reports',
            element: <Reports />,
          },
          {
            path: '/admin',
            element: <AdminDashboard />,
          },
          {
            path: '/activity-log',
            element: <ActivityLog />,
          },
          {
            path: '/import-export',
            element: <ImportExport />,
          },
          {
            path: '/settings',
            element: <Settings />,
          },
          {
            path: '/whatsapp-logs',
            element: <WhatsAppLogs />,
          },
          {
            path: '/calendar',
            element: <Calendar />,
          },
          {
            path: '/messaging',
            element: <BulkMessaging />,
          },
          {
            path: '/reminders',
            element: <Reminders />,
          },
          {
            path: '/integrations',
            element: <IntegrationTest />,
          },
        ],
      },
    ],
  },
]);

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Suspense fallback={<PageLoader />}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </Suspense>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
