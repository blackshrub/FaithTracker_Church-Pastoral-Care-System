import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import './i18n';
import '@/App.css';
import { Dashboard } from '@/pages/Dashboard';
import { MembersList } from '@/pages/MembersList';
import { MemberDetail } from '@/pages/MemberDetail';
import { FinancialAid } from '@/pages/FinancialAid';
import { Analytics } from '@/pages/Analytics';
import { IntegrationTest } from '@/components/IntegrationTest';
import { Layout } from '@/components/Layout';

function App() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading...</div>}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/members" element={<MembersList />} />
            <Route path="/members/:id" element={<MemberDetail />} />
            <Route path="/financial-aid" element={<FinancialAid />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/integrations" element={<IntegrationTest />} />
          </Routes>
        </Layout>
        <Toaster />
      </BrowserRouter>
    </Suspense>
  );
}

export default App;