import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import './i18n';
import '@/App.css';
import LoginPage from '@/pages/LoginPage';

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
const IntegrationTest = lazy(() => import('@/components/IntegrationTest'));
const Layout = lazy(() => import('@/components/Layout'));

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

function AppRoutes() {
  const { user } = useAuth();
  
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
      <Route path="/import-export" element={<ProtectedRoute><Layout><ImportExport /></Layout></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><Layout><SettingsPage /></Layout></ProtectedRoute>} />
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
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading...</div>}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </Suspense>
  );
}

export default App;