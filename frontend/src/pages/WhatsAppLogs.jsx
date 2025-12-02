import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { RefreshCw, Send, AlertCircle, CheckCircle2 } from 'lucide-react';
import { format } from 'date-fns/format';

const formatDate = (dateStr, formatStr = 'dd MMM yyyy HH:mm') => {
  try {
    return format(new Date(dateStr), formatStr);
  } catch (e) {
    return dateStr;
  }
};

export const WhatsAppLogs = () => {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(null);
  
  useEffect(() => {
    loadLogs();
  }, []);
  
  const loadLogs = async () => {
    try {
      setLoading(true);
      const response = await api.get('/notification-logs?limit=100');
      setLogs(response.data);
    } catch (error) {
      toast.error(t('whatsapp_logs_page.failed_load_logs'));
    } finally {
      setLoading(false);
    }
  };
  
  const retryFailed = async (log) => {
    try {
      setRetrying(log.id);
      // Retry by resending the same message
      const response = await api.post('/integrations/ping/whatsapp', {
        phone: log.recipient.replace('@s.whatsapp.net', ''),
        message: log.message
      });
      
      if (response.data.success) {
        toast.success(t('whatsapp_logs_page.message_sent'));
        loadLogs();
      } else {
        toast.error(t('whatsapp_logs_page.failed_send'));
      }
    } catch (error) {
      toast.error('Retry failed');
    } finally {
      setRetrying(null);
    }
  };
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('whatsapp_logs_page.title')}</h1>
          <p className="text-muted-foreground mt-1">View and retry failed messages</p>
        </div>
        <Button onClick={loadLogs} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />Refresh
        </Button>
      </div>
      
      <Card>
        <CardHeader>
          <CardTitle>{t('whatsapp_logs_page.recent_notifications')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Recipient</TableHead>
                  <TableHead>Message Preview</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">No notifications yet</TableCell>
                  </TableRow>
                ) : (
                  logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDate(log.created_at)}
                      </TableCell>
                      <TableCell>{log.recipient}</TableCell>
                      <TableCell>
                        <div className="max-w-md truncate text-sm">{log.message}</div>
                      </TableCell>
                      <TableCell>
                        {log.status === 'sent' ? (
                          <Badge className="bg-green-100 text-green-700">
                            <CheckCircle2 className="w-3 h-3 mr-1" />Sent
                          </Badge>
                        ) : (
                          <Badge className="bg-red-100 text-red-700">
                            <AlertCircle className="w-3 h-3 mr-1" />Failed
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="outline"
                          className="bg-teal-500 text-white hover:bg-teal-600"
                          onClick={() => retryFailed(log)}
                          disabled={retrying === log.id}
                        >
                          <Send className="w-3 h-3 mr-1" />
                          {retrying === log.id ? 'Sending...' : 'Resend'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default WhatsAppLogs;