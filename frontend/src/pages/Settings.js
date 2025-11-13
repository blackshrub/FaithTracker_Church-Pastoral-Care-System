import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Settings as SettingsIcon, Bell, Heart, Zap } from 'lucide-react';

export const Settings = () => {
  const { user } = useAuth();
  const [atRiskDays, setAtRiskDays] = useState(60);
  const [inactiveDays, setInactiveDays] = useState(90);
  const [griefStages, setGriefStages] = useState([
    { stage: '1_week', days: 7, name: '1 Week After' },
    { stage: '2_weeks', days: 14, name: '2 Weeks After' },
    { stage: '1_month', days: 30, name: '1 Month After' },
    { stage: '3_months', days: 90, name: '3 Months After' },
    { stage: '6_months', days: 180, name: '6 Months After' },
    { stage: '1_year', days: 365, name: '1 Year After' },
  ]);
  
  const saveEngagementSettings = () => {
    // Would save to backend/database in production
    localStorage.setItem('engagement_settings', JSON.stringify({ atRiskDays, inactiveDays }));
    toast.success('Engagement thresholds saved!');
  };
  
  const saveGriefStages = () => {
    // Would save to backend/database in production
    localStorage.setItem('grief_stages', JSON.stringify(griefStages));
    toast.success('Grief stages configuration saved!');
  };
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings & Configuration</h1>
        <p className="text-muted-foreground mt-1">System configuration and automation settings</p>
      </div>
      
      <Tabs defaultValue="automation">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="automation"><Bell className="w-4 h-4 mr-2" />Automation</TabsTrigger>
          <TabsTrigger value="grief"><Heart className="w-4 h-4 mr-2" />Grief Support</TabsTrigger>
          <TabsTrigger value="engagement"><Users className="w-4 h-4 mr-2" />Engagement</TabsTrigger>
          <TabsTrigger value="system"><SettingsIcon className="w-4 h-4 mr-2" />System</TabsTrigger>
        </TabsList>
        
        <TabsContent value="automation">
          <Card>
            <CardHeader>
              <CardTitle>Daily Digest Configuration</CardTitle>
              <CardDescription>Configure automated daily reminders to pastoral team</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Schedule Time</Label>
                <Input value="08:00" disabled />
                <p className="text-xs text-muted-foreground mt-1">Jakarta Time (UTC+7) - Currently fixed</p>
              </div>
              <div>
                <Label>WhatsApp Gateway URL</Label>
                <Input value={process.env.REACT_APP_WHATSAPP_GATEWAY_URL || "http://dermapack.net:3001"} disabled />
                <p className="text-xs text-muted-foreground mt-1">Change in backend .env file</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="font-medium text-sm">📋 What Gets Sent:</p>
                <ul className="text-sm mt-2 space-y-1">
                  <li>🎂 Birthdays today + this week (with phone numbers)</li>
                  <li>💔 Grief support stages due for follow-up</li>
                  <li>🏥 Hospital discharge follow-ups (3, 7, 14 days after)</li>
                  <li>⚠️ Members at risk (30+ days no contact)</li>
                </ul>
                <p className="text-sm mt-2 font-medium">📱 Sent To:</p>
                <p className="text-sm">All pastoral team members (campus admins + pastors) for their assigned campus. Full admin receives digest for ALL campuses.</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="grief">
          <Card>
            <CardHeader>
              <CardTitle>Grief Support Timeline Configuration</CardTitle>
              <CardDescription>Customize the 6-stage grief support schedule</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {griefStages.map((stage, index) => (
                <div key={stage.stage} className="flex items-center gap-4 p-3 bg-muted/30 rounded">
                  <span className="font-medium w-32">{stage.name}</span>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      value={stage.days}
                      onChange={(e) => {
                        const updated = [...griefStages];
                        updated[index].days = parseInt(e.target.value);
                        setGriefStages(updated);
                      }}
                      className="w-20"
                    />
                    <span className="text-sm text-muted-foreground">days after mourning</span>
                  </div>
                </div>
              ))}
              <Button onClick={saveGriefStages} className="bg-teal-500 hover:bg-teal-600 text-white">
                Save Grief Stages Configuration
              </Button>
              <div className="p-4 bg-purple-50 rounded-lg mt-4">
                <p className="text-sm font-medium">💜 Note:</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Changes will apply to NEW grief events. Existing timelines remain unchanged.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="engagement">
          <Card>
            <CardHeader>
              <CardTitle>Engagement Status Thresholds</CardTitle>
              <CardDescription>Configure when members are marked at-risk or inactive</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>At Risk Threshold (days since last contact)</Label>
                <Input
                  type="number"
                  value={atRiskDays}
                  onChange={(e) => setAtRiskDays(parseInt(e.target.value))}
                  min="1"
                />
                <p className="text-xs text-muted-foreground">Default: 60 days. Members with no contact for this many days will show as "At Risk"</p>
              </div>
              <div className="space-y-2">
                <Label>Inactive Threshold (days since last contact)</Label>
                <Input
                  type="number"
                  value={inactiveDays}
                  onChange={(e) => setInactiveDays(parseInt(e.target.value))}
                  min="1"
                />
                <p className="text-xs text-muted-foreground">Default: 90 days. Members with no contact for this many days will show as "Inactive"</p>
              </div>
              <Button onClick={saveEngagementSettings} className="bg-teal-500 hover:bg-teal-600 text-white">
                Save Engagement Thresholds
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="system">
          <Card>
            <CardHeader>
              <CardTitle>System Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Church Name</Label>
                <Input value="GKBJ" disabled />
              </div>
              <div>
                <Label>Database</Label>
                <Input value="pastoral_care_db" disabled />
              </div>
              <div>
                <Label>Total Campuses</Label>
                <Input value="115" disabled />
              </div>
              <div>
                <Label>Your Role</Label>
                <Input value={user?.role === 'full_admin' ? 'Full Administrator' : user?.role === 'campus_admin' ? 'Campus Admin' : 'Pastor'} disabled />
              </div>
              {user?.campus_name && (
                <div>
                  <Label>Your Campus</Label>
                  <Input value={user.campus_name} disabled />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Settings;