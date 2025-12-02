/**
 * App.js - Root React component and routing
 * Sets up React Query, authentication context, and application routes
 */

import React, { Suspense, lazy, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import PageLoader from '@/components/PageLoader';
import './i18n';
import '@/App.css';
import LoginPage from '@/pages/LoginPage';
import api from '@/lib/api';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // Data considered fresh for 30 seconds
      cacheTime: 1000 * 60 * 5, // Keep unused data in cache for 5 minutes
      refetchOnWindowFocus: true, // Refetch when user returns to tab
      retry: 1, // Retry failed requests once
    },
    mutations: {
      retry: 1,
    },
  },
});

// Lazy load components
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const MembersList = lazy(() => import('@/pages/MembersList'));
const MemberDetail = lazy(() => import('@/pages/MemberDetail'));
const FinancialAid = lazy(() => import('@/pages/FinancialAid'));
const Analytics = lazy(() => import('@/pages/Analytics'));
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

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <PageLoader />;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

function AppRoutes() {
  const { user } = useAuth();
  const [needsSetup, setNeedsSetup] = useState(null);
  
  // Check if setup is needed
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
  
  // Show loading while checking
  if (needsSetup === null) {
    return <PageLoader />;
  }
  
  // Show setup wizard if needed
  if (needsSetup) {
    return <SetupWizard onComplete={() => setNeedsSetup(false)} />;
  }
  
  return (
    <Routes>
      <Route path="/login" element={!user ? <LoginPage /> : <Navigate to="/dashboard" replace />} />
      <Route path="/" element={<ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>} />
      <Route path="/members" element={<ProtectedRoute><Layout><MembersList /></Layout></ProtectedRoute>} />
      <Route path="/members/:id" element={<ProtectedRoute><Layout><MemberDetail /></Layout></ProtectedRoute>} />
      <Route path="/financial-aid" element={<ProtectedRoute><Layout><FinancialAid /></Layout></ProtectedRoute>} />
      <Route path="/analytics" element={<ProtectedRoute><Layout><Analytics /></Layout></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute><Layout><AdminDashboard /></Layout></ProtectedRoute>} />
      <Route path="/activity-log" element={<ProtectedRoute><Layout><ActivityLog /></Layout></ProtectedRoute>} />
      <Route path="/import-export" element={<ProtectedRoute><Layout><ImportExport /></Layout></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><Layout><Settings /></Layout></ProtectedRoute>} />
      <Route path="/whatsapp-logs" element={<ProtectedRoute><Layout><WhatsAppLogs /></Layout></ProtectedRoute>} />
      <Route path="/calendar" element={<ProtectedRoute><Layout><Calendar /></Layout></ProtectedRoute>} />
      <Route path="/messaging" element={<ProtectedRoute><Layout><BulkMessaging /></Layout></ProtectedRoute>} />
      <Route path="/reminders" element={<ProtectedRoute><Layout><Reminders /></Layout></ProtectedRoute>} />
      <Route path="/integrations" element={<ProtectedRoute><Layout><IntegrationTest /></Layout></ProtectedRoute>} />
    </Routes>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Suspense fallback={<PageLoader />}>
          <BrowserRouter>
            <AuthProvider>
              <AppRoutes />
              <Toaster />
            </AuthProvider>
          </BrowserRouter>
        </Suspense>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;