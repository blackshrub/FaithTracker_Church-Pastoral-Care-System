import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { Send, Users } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

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
      const response = await axios.get(`${API}/users`);
      setUsers(response.data);
    } catch (error) {
      toast.error(t('bulk_messaging.failed_load_users'));
    }
  };
  
  const handleSendBulk = async () => {
    if (selectedUsers.length === 0) {
      toast.error(t('bulk_messaging.select_recipient'));
      return;
    }
    if (!message.trim()) {
      toast.error(t('bulk_messaging.enter_message'));
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
            
            const response = await axios.post(`${API}/integrations/ping/whatsapp`, {
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
      
      toast.success(`Sent to ${sent} recipients, ${failed} failed`);
      setMessage('');
      setSelectedUsers([]);
    } catch (error) {
      toast.error('Bulk send failed');
    } finally {
      setSending(false);
    }
  };
  
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-playfair font-bold">Bulk Messaging</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Select Recipients</CardTitle>
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
            <CardTitle>Compose Message</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground mb-2">{selectedUsers.length} recipients selected</p>
              <Textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Type your message to pastoral team..."
                rows={8}
              />
            </div>
            <Button
              className="w-full bg-teal-500 hover:bg-teal-600"
              onClick={handleSendBulk}
              disabled={sending || selectedUsers.length === 0 || !message.trim()}
            >
              <Send className="w-4 h-4 mr-2" />
              {sending ? 'Sending...' : `Send to ${selectedUsers.length} Recipients`}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BulkMessaging;