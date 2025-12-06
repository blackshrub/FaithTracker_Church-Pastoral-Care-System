import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Send, Users } from 'lucide-react';

import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';

export const BulkMessaging = () => {
  const { t } = useTranslation();
  const [users, setUsers] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  
  useEffect(() => {
    loadUsers();
  }, []);
  
  const loadUsers = async () => {
    try {
      const response = await api.get(`/users`);
      setUsers(response.data);
    } catch (_error) {
      toast.error(t('bulk_messaging_page.failed_load_users'));
    }
  };
  
  const handleSendBulk = async () => {
    if (selectedUsers.length === 0) {
      toast.error(t('bulk_messaging_page.select_recipient'));
      return;
    }
    if (!message.trim()) {
      toast.error(t('bulk_messaging_page.enter_message'));
      return;
    }
    
    try {
      setSending(true);
      let sent = 0;
      let failed = 0;
      
      for (const userId of selectedUsers) {
        const user = users.find(u => u.id === userId);
        if (user) {
          try {
            // Format phone for WhatsApp (add @s.whatsapp.net if not present)
            let phone = user.phone;
            if (phone && !phone.includes('@s.whatsapp.net')) {
              // Ensure it starts with country code
              if (phone.startsWith('0')) {
                phone = '62' + phone.substring(1);
              } else if (phone.startsWith('+')) {
                phone = phone.substring(1);
              }
              phone = phone + '@s.whatsapp.net';
            }
            
            const response = await api.post(`/integrations/ping/whatsapp`, {
              phone: phone,
              message
            });
            if (response.data.success) sent++;
            else failed++;
          } catch {
            failed++;
          }
        }
      }
      
      toast.success(t('bulk_messaging_page.sent_results', {sent, failed}));
      setMessage('');
      setSelectedUsers([]);
    } catch (_error) {
      toast.error(t('bulk_messaging_page.bulk_send_failed'));
    } finally {
      setSending(false);
    }
  };
  
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-playfair font-bold">{t('bulk_messaging_page.title')}</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>{t('bulk_messaging_page.select_recipients')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {users.map(user => (
                <div key={user.id} className="flex items-center gap-3 p-2 hover:bg-muted rounded">
                  <Checkbox
                    checked={selectedUsers.includes(user.id)}
                    onCheckedChange={(checked) => {
                      setSelectedUsers(checked 
                        ? [...selectedUsers, user.id]
                        : selectedUsers.filter(id => id !== user.id)
                      );
                    }}
                  />
                  <div>
                    <p className="font-semibold text-sm">{user.name}</p>
                    <p className="text-xs text-muted-foreground">{user.phone}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>{t('bulk_messaging_page.compose_message')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground mb-2">{t('bulk_messaging_page.recipients_selected', {count: selectedUsers.length})}</p>
              <Textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={t('bulk_messaging_page.type_message_placeholder')}
                rows={8}
              />
            </div>
            <Button
              className="w-full bg-teal-500 hover:bg-teal-600"
              onClick={handleSendBulk}
              disabled={sending || selectedUsers.length === 0 || !message.trim()}
            >
              <Send className="w-4 h-4 mr-2" />
              {sending ? t('bulk_messaging_page.sending') : t('bulk_messaging_page.send_to_recipients', {count: selectedUsers.length})}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BulkMessaging;