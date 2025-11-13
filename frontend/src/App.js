import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import './i18n';
import '@/App.css';
import LoginPage from '@/pages/LoginPage';
import { Dashboard } from '@/pages/Dashboard';
import { MembersList } from '@/pages/MembersList';
import { MemberDetail } from '@/pages/MemberDetail';
import { FinancialAid } from '@/pages/FinancialAid';
import { Analytics } from '@/pages/Analytics';
import { AdminDashboard } from '@/pages/AdminDashboard';
import { IntegrationTest } from '@/components/IntegrationTest';
import { Layout } from '@/components/Layout';

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