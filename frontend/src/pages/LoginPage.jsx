import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Heart, LogIn } from 'lucide-react';

import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';

export const LoginPage = () => {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [campusId, setCampusId] = useState('');
  const [campuses, setCampuses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingCampuses, setLoadingCampuses] = useState(true);
  const [error, setError] = useState('');
  
  useEffect(() => {
    loadCampuses();
  }, []);
  
  const loadCampuses = async () => {
    try {
      const response = await api.get('/campuses');
      // Ensure we always set an array
      const data = response.data;
      setCampuses(Array.isArray(data) ? data : (data?.campuses || []));
    } catch (error) {
      console.error('Error loading campuses:', error);
      setCampuses([]);
    } finally {
      setLoadingCampuses(false);
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    // Validate campus selection
    if (!campusId) {
      setError('Please select a campus');
      return;
    }
    
    setLoading(true);
    
    try {
      await login(email, password, campusId);
      toast.success('Login successful!');
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <Card className="w-full max-w-md shadow-lg" data-testid="login-card">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <Heart className="h-12 w-12 text-primary-500" fill="currentColor" />
          </div>
          <CardTitle className="text-2xl font-manrope font-bold">{t('app_title')}</CardTitle>
          <CardDescription>{t('login_page.sign_in_subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert className="border-red-500 bg-red-50" data-testid="login-error">
                <AlertDescription className="text-red-700">{error}</AlertDescription>
              </Alert>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="campus">Campus / Gereja</Label>
              {loadingCampuses ? (
                <div className="text-sm text-muted-foreground">Loading campuses...</div>
              ) : (
                <Select value={campusId} onValueChange={setCampusId}>
                  <SelectTrigger data-testid="campus-select">
                    <SelectValue placeholder={t('login_page.select_campus_placeholder')} />
                  </SelectTrigger>
                  <SelectContent className="max-h-[300px] overflow-y-auto">
                    {campuses.map((campus) => (
                      <SelectItem key={campus.id} value={campus.id}>
                        {campus.campus_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <p className="text-xs text-muted-foreground">{t('login_page.select_campus_required')}</p>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('login_page.email_placeholder')}
                required
                data-testid="login-email-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t('login_page.password_placeholder')}
                required
                data-testid="login-password-input"
              />
            </div>
            
            <Button
              type="submit"
              className="w-full bg-teal-500 hover:bg-teal-600 text-white"
              loading={loading}
              data-testid="login-button"
            >
              <LogIn className="w-4 h-4 mr-2" /> Sign In
            </Button>
            
            <div className="text-center text-sm text-muted-foreground mt-4">
              <p className="text-xs">{t('login_page.campus_management_hint')}</p>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default LoginPage;