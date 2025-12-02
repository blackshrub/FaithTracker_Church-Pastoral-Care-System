/**
 * SetupWizard - First-run setup for FaithTracker
 * Guides user through creating first admin account and campus
 */

import React, { useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Church } from 'lucide-react';

const SetupWizard = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [adminData, setAdminData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    phone: ''
  });
  const [campusData, setCampusData] = useState({
    campus_name: '',
    location: '',
    timezone: 'Asia/Jakarta'
  });

  const createAdmin = async () => {
    try {
      if (adminData.password !== adminData.confirmPassword) {
        toast.error('Passwords do not match');
        return;
      }

      await axios.post(`${import.meta.env.VITE_BACKEND_URL}/setup/admin`, {
        email: adminData.email,
        password: adminData.password,
        name: adminData.name,
        phone: adminData.phone
      });

      toast.success('Admin account created');
      setStep(2);
    } catch (error) {
      toast.error('Failed to create admin: ' + (error.response?.data?.detail || error.message));
    }
  };

  const createCampus = async () => {
    try {
      await axios.post(`${import.meta.env.VITE_BACKEND_URL}/setup/campus`, campusData);
      toast.success('Campus created successfully');
      setStep(3);
      setTimeout(() => onComplete(), 2000);
    } catch (error) {
      toast.error('Failed to create campus: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 to-blue-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-teal-500 rounded-full flex items-center justify-center mb-4">
            <Church className="w-10 h-10 text-white" />
          </div>
          <CardTitle className="text-2xl">Welcome to FaithTracker!</CardTitle>
          <CardDescription>
            Let's set up your pastoral care system
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Step 1: Create Admin */}
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg">Step 1: Create Admin Account</h3>
              <div>
                <Label>Full Name</Label>
                <Input
                  value={adminData.name}
                  onChange={(e) => setAdminData({...adminData, name: e.target.value})}
                  placeholder="John Doe"
                />
              </div>
              <div>
                <Label>Email</Label>
                <Input
                  type="email"
                  value={adminData.email}
                  onChange={(e) => setAdminData({...adminData, email: e.target.value})}
                  placeholder="admin@church.org"
                />
              </div>
              <div>
                <Label>Phone Number (WhatsApp)</Label>
                <Input
                  type="tel"
                  value={adminData.phone}
                  onChange={(e) => setAdminData({...adminData, phone: e.target.value})}
                  placeholder="+6281234567890 or 081234567890"
                />
              </div>
              <div>
                <Label>Password</Label>
                <Input
                  type="password"
                  value={adminData.password}
                  onChange={(e) => setAdminData({...adminData, password: e.target.value})}
                  placeholder="Minimum 8 characters"
                />
              </div>
              <div>
                <Label>Confirm Password</Label>
                <Input
                  type="password"
                  value={adminData.confirmPassword}
                  onChange={(e) => setAdminData({...adminData, confirmPassword: e.target.value})}
                  placeholder="Re-enter password"
                />
              </div>
              <Button 
                onClick={createAdmin}
                className="w-full bg-teal-500 hover:bg-teal-600"
                disabled={!adminData.name || !adminData.email || !adminData.phone || !adminData.password || adminData.password.length < 8}
              >
                Create Admin Account
              </Button>
            </div>
          )}

          {/* Step 2: Create Campus */}
          {step === 2 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg">Step 2: Create First Campus</h3>
              <div>
                <Label>Campus Name</Label>
                <Input
                  value={campusData.campus_name}
                  onChange={(e) => setCampusData({...campusData, campus_name: e.target.value})}
                  placeholder="Downtown Campus"
                />
              </div>
              <div>
                <Label>Location (Address)</Label>
                <Input
                  value={campusData.location}
                  onChange={(e) => setCampusData({...campusData, location: e.target.value})}
                  placeholder="123 Main Street, City"
                />
              </div>
              <div>
                <Label>Timezone</Label>
                <select
                  className="w-full border rounded p-2"
                  value={campusData.timezone}
                  onChange={(e) => setCampusData({...campusData, timezone: e.target.value})}
                >
                  <option value="Asia/Jakarta">Asia/Jakarta (UTC+7)</option>
                  <option value="Asia/Singapore">Asia/Singapore (UTC+8)</option>
                  <option value="Asia/Tokyo">Asia/Tokyo (UTC+9)</option>
                  <option value="America/New_York">America/New_York (UTC-5)</option>
                  <option value="Europe/London">Europe/London (UTC+0)</option>
                </select>
              </div>
              <Button 
                onClick={createCampus}
                className="w-full bg-teal-500 hover:bg-teal-600"
                disabled={!campusData.campus_name}
              >
                Create Campus
              </Button>
            </div>
          )}

          {/* Step 3: Complete */}
          {step === 3 && (
            <div className="text-center py-8">
              <h3 className="font-semibold text-xl mb-4 text-green-600">✓ Setup Complete!</h3>
              <p className="text-gray-600 mb-4">Redirecting to login...</p>
            </div>
          )}

          {/* Progress */}
          <div className="mt-6 flex justify-center gap-2">
            <div className={`w-3 h-3 rounded-full ${step >= 1 ? 'bg-teal-500' : 'bg-gray-300'}`}></div>
            <div className={`w-3 h-3 rounded-full ${step >= 2 ? 'bg-teal-500' : 'bg-gray-300'}`}></div>
            <div className={`w-3 h-3 rounded-full ${step >= 3 ? 'bg-teal-500' : 'bg-gray-300'}`}></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SetupWizard;
