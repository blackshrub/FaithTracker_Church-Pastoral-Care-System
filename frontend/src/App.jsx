/**
 * App.jsx - Root React component and routing
 * Sets up React Query, authentication context, and application routes
 *
 * Performance optimizations:
 * - Route-level data prefetching with React Router loaders
 * - Lazy loading for all pages
 * - React Compiler enabled for automatic memoization
 */

import React, { Suspense, lazy, useState, useEffect } from 'react';
import {
  createBrowserRouter,
  RouterProvider,
  Navigate,
  Outlet,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import PageLoader from '@/components/PageLoader';
import {
  setQueryClient,
  dashboardLoader,
  membersLoader,
  memberDetailLoader,
  analyticsLoader,
  financialAidLoader,
  adminLoader,
  activityLogLoader,
  reportsLoader,
} from '@/lib/routeLoaders';
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

// Set query client for route loaders
setQueryClient(queryClient);

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

// Create router with data loaders for parallel data fetching
const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: '/login',
        element: <LoginRoute />,
      },
      {
        element: <ProtectedRoute />,
        children: [
          {
            path: '/',
            element: <Dashboard />,
            loader: dashboardLoader,
          },
          {
            path: '/dashboard',
            element: <Dashboard />,
            loader: dashboardLoader,
          },
          {
            path: '/members',
            element: <MembersList />,
            loader: membersLoader,
          },
          {
            path: '/members/:id',
            element: <MemberDetail />,
            loader: memberDetailLoader,
          },
          {
            path: '/financial-aid',
            element: <FinancialAid />,
            loader: financialAidLoader,
          },
          {
            path: '/analytics',
            element: <Analytics />,
            loader: analyticsLoader,
          },
          {
            path: '/reports',
            element: <Reports />,
            loader: reportsLoader,
          },
          {
            path: '/admin',
            element: <AdminDashboard />,
            loader: adminLoader,
          },
          {
            path: '/activity-log',
            element: <ActivityLog />,
            loader: activityLogLoader,
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
