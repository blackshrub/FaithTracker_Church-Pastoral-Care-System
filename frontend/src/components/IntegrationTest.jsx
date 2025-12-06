import { useState } from 'react';
import { Loader2, CheckCircle2, XCircle, MessageSquare, Mail } from 'lucide-react';

import api from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';

export const IntegrationTest = () => {
  const [whatsappPhone, setWhatsappPhone] = useState('6281290080025');
  const [whatsappMessage, setWhatsappMessage] = useState('Test message from GKBJ Pastoral Care System');
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [whatsappResult, setWhatsappResult] = useState(null);
  
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailResult, setEmailResult] = useState(null);

  const testWhatsApp = async () => {
    setWhatsappLoading(true);
    setWhatsappResult(null);

    try {
      const response = await api.post('/integrations/ping/whatsapp', {
        phone: whatsappPhone,
        message: whatsappMessage
      });

      setWhatsappResult(response.data);
    } catch (error) {
      setWhatsappResult({
        success: false,
        message: error.response?.data?.detail || error.message || 'Unknown error',
        details: error.response?.data
      });
    } finally {
      setWhatsappLoading(false);
    }
  };

  const testEmail = async () => {
    setEmailLoading(true);
    setEmailResult(null);

    try {
      const response = await api.get('/integrations/ping/email');
      setEmailResult(response.data);
    } catch (error) {
      setEmailResult({
        success: false,
        message: error.response?.data?.detail || error.message || 'Unknown error'
      });
    } finally {
      setEmailLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-foreground">Integration Testing</h1>
          <p className="text-muted-foreground">Test WhatsApp and Email notification integrations</p>
        </div>

        {/* WhatsApp Test Card */}
        <Card data-testid="whatsapp-test-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-primary" />
              WhatsApp Gateway Test
            </CardTitle>
            <CardDescription>
              Test the WhatsApp integration with your gateway at http://dermapack.net:3001
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="whatsapp-phone">Phone Number (with country code)</Label>
              <Input
                id="whatsapp-phone"
                type="text"
                value={whatsappPhone}
                onChange={(e) => setWhatsappPhone(e.target.value)}
                placeholder="628123456789"
                data-testid="whatsapp-phone-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="whatsapp-message">Test Message</Label>
              <Input
                id="whatsapp-message"
                type="text"
                value={whatsappMessage}
                onChange={(e) => setWhatsappMessage(e.target.value)}
                placeholder="Enter test message"
                data-testid="whatsapp-message-input"
              />
            </div>

            <Button 
              onClick={testWhatsApp} 
              disabled={whatsappLoading || !whatsappPhone || !whatsappMessage}
              className="w-full"
              data-testid="whatsapp-test-button"
            >
              {whatsappLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {whatsappLoading ? 'Sending...' : 'Send Test WhatsApp'}
            </Button>

            {whatsappResult && (
              <Alert 
                className={whatsappResult.success ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'}
                data-testid="whatsapp-result"
              >
                {whatsappResult.success ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
                <AlertDescription className="ml-2">
                  <div className="font-medium">{whatsappResult.message}</div>
                  {whatsappResult.details && (
                    <div className="mt-2 text-xs">
                      <pre className="bg-white p-2 rounded border overflow-auto">
                        {JSON.stringify(whatsappResult.details, null, 2)}
                      </pre>
                    </div>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Email Test Card */}
        <Card data-testid="email-test-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-primary" />
              Email Integration Test
            </CardTitle>
            <CardDescription>
              Test the email notification integration (currently pending provider setup)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button 
              onClick={testEmail} 
              disabled={emailLoading}
              className="w-full"
              data-testid="email-test-button"
            >
              {emailLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {emailLoading ? 'Checking...' : 'Check Email Status'}
            </Button>

            {emailResult && (
              <Alert 
                className={emailResult.pending_provider ? 'border-yellow-500 bg-yellow-50' : 'border-red-500 bg-red-50'}
                data-testid="email-result"
              >
                {emailResult.pending_provider ? (
                  <Mail className="h-4 w-4 text-yellow-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
                <AlertDescription className="ml-2">
                  <div className="font-medium">{emailResult.message}</div>
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <div className="text-center text-sm text-muted-foreground">
          <p>🏥 GKBJ Pastoral Care System - Integration Testing Tool</p>
        </div>
      </div>
    </div>
  );
};
