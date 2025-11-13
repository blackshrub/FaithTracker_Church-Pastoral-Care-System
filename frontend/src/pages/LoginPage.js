import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';
import { Heart, LogIn, Loader2 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

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
      const response = await axios.get(`${API}/campuses`);
      setCampuses(response.data);
    } catch (error) {
      console.error('Error loading campuses:', error);
    } finally {
      setLoadingCampuses(false);
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      await login(email, password, campusId || null);
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
          <CardDescription>Sign in to access the pastoral care system</CardDescription>
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
                    <SelectValue placeholder="Select your campus (optional for full admin)" />
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
              <p className="text-xs text-muted-foreground">Select campus (required for campus admin/pastor)</p>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@gkbj.church"
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
                placeholder="Enter your password"
                required
                data-testid="login-password-input"
              />
            </div>
            
            <Button 
              type="submit" 
              className="w-full bg-teal-500 hover:bg-teal-600 text-white"
              disabled={loading}
              data-testid="login-button"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Signing in...</>
              ) : (
                <><LogIn className="w-4 h-4 mr-2" /> Sign In</>
              )}
            </Button>
            
            <div className="text-center text-sm text-muted-foreground mt-4">
              <p>Full Admin: admin@gkbj.church / admin123</p>
              <p className="text-xs mt-1">Full admin can access all campuses</p>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default LoginPage;