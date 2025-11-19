import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Settings as SettingsIcon, Bell, Heart, Zap, Users, Clock, UserCircle, Upload } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const Settings = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [atRiskDays, setAtRiskDays] = useState(60);
  const [inactiveDays, setInactiveDays] = useState(90);
  const [campusCount, setCampusCount] = useState(0);
  const [campusTimezone, setCampusTimezone] = useState('Asia/Jakarta');
  const [writeoffBirthday, setWriteoffBirthday] = useState(7);
  const [writeoffFinancialAid, setWriteoffFinancialAid] = useState(0);
  const [writeoffAccident, setWriteoffAccident] = useState(14);
  const [writeoffGrief, setWriteoffGrief] = useState(14);
  const [activeTab, setActiveTab] = useState('automation');
  const [griefStages, setGriefStages] = useState([
    { stage: '1_week', days: 7, name: '1 Week After' },
    { stage: '2_weeks', days: 14, name: '2 Weeks After' },
    { stage: '1_month', days: 30, name: '1 Month After' },
    { stage: '3_months', days: 90, name: '3 Months After' },
    { stage: '6_months', days: 180, name: '6 Months After' },
    { stage: '1_year', days: 365, name: '1 Year After' },
  ]);
  const [accidentFollowUp, setAccidentFollowUp] = useState([
    { stage: 'first_followup', days: 3, name: 'First Follow-up' },
    { stage: 'second_followup', days: 7, name: 'Second Follow-up' },
    { stage: 'final_followup', days: 14, name: 'Final Follow-up' },
  ]);
  const [uploading, setUploading] = useState(false);
  
  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API}/users/${user.id}/photo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      toast.success('Profile photo updated successfully');
      
      // Reload user data
      window.location.reload();
    } catch (error) {
      toast.error('Failed to upload photo');
      console.error('Photo upload error:', error);
    } finally {
      setUploading(false);
    }
  };

  
  useEffect(() => {
    loadCampusCount();
  }, []);
  
  const loadCampusCount = async () => {
    try {
      const response = await axios.get(`${API}/campuses`);
      setCampusCount(response.data.length);
      
      // Load timezone from user's campus
      if (user?.campus_id) {
        const campusRes = await axios.get(`${API}/campuses/${user.campus_id}`);
        setCampusTimezone(campusRes.data.timezone || 'Asia/Jakarta');
      }
      
      // Load writeoff settings
      const writeoffRes = await axios.get(`${API}/settings/overdue_writeoff`);
      if (writeoffRes.data?.data) {
        setWriteoffBirthday(writeoffRes.data.data.birthday || 7);
        setWriteoffFinancialAid(writeoffRes.data.data.financial_aid || 0);
        setWriteoffAccident(writeoffRes.data.data.accident_illness || 14);
        setWriteoffGrief(writeoffRes.data.data.grief_support || 14);
      }
    } catch (error) {
      console.error('Error loading settings');
    }
  };
  
  const saveWriteoffSettings = async () => {
    try {
      await axios.put(`${API}/settings/overdue_writeoff`, {
        data: {
          birthday: parseInt(writeoffBirthday),
          financial_aid: parseInt(writeoffFinancialAid),
          accident_illness: parseInt(writeoffAccident),
          grief_support: parseInt(writeoffGrief)
        }
      });
      toast.success(t('toasts.writeoff_saved'));
    } catch (error) {
      toast.error(t('toasts.failed_save_writeoff'));
      console.error('Error saving writeoff settings:', error);
    }
  };
  
  const saveTimezoneSettings = async () => {
    try {
      if (!user?.campus_id) {
        toast.error('No campus assigned to user');
        return;
      }
      
      await axios.put(`${API}/campuses/${user.campus_id}`, {
        timezone: campusTimezone
      });
      toast.success(t('toasts.timezone_saved'));
    } catch (error) {
      toast.error(t('toasts.failed_save_timezone'));
      console.error('Error saving timezone:', error);
    }
  };
  
  const saveEngagementSettings = () => {
    // Would save to backend/database in production
    localStorage.setItem('engagement_settings', JSON.stringify({ atRiskDays, inactiveDays }));
    toast.success(t('toasts.engagement_saved'));
  };
  
  const saveGriefStages = () => {
    // Would save to backend/database in production
    localStorage.setItem('grief_stages', JSON.stringify(griefStages));
    toast.success(t('toasts.grief_stages_saved'));
  };
  
  const saveAccidentFollowUp = () => {
    localStorage.setItem('accident_followup', JSON.stringify(accidentFollowUp));
    toast.success(t('toasts.accident_config_saved'));
  };
  
  return (
    <div className="space-y-6 max-w-full">
      <div className="min-w-0">
        <h1 className="text-3xl font-playfair font-bold">{t('settings_page.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('settings_page.subtitle')}</p>
      </div>
      
      <Tabs defaultValue="automation" className="max-w-full" onValueChange={(v) => setActiveTab(v)}>
        <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex min-w-full w-max sm:w-full">
            <TabsTrigger value="automation" className="flex-shrink-0">
              <Bell className="w-4 h-4" />
              {activeTab === 'automation' && <span className="ml-2">{t('settings_page.automation_tab')}</span>}
            </TabsTrigger>
            <TabsTrigger value="grief" className="flex-shrink-0">
              <Heart className="w-4 h-4" />
              {activeTab === 'grief' && <span className="ml-2">{t('settings_page.grief_tab')}</span>}
            </TabsTrigger>
            <TabsTrigger value="accident" className="flex-shrink-0">
              <Zap className="w-4 h-4" />
              {activeTab === 'accident' && <span className="ml-2">{t('settings_page.accident_tab')}</span>}
            </TabsTrigger>
            <TabsTrigger value="engagement" className="flex-shrink-0">
              <Users className="w-4 h-4" />
              {activeTab === 'engagement' && <span className="ml-2">{t('settings_page.engagement_tab')}</span>}
            </TabsTrigger>
            <TabsTrigger value="writeoff" className="flex-shrink-0">
              <Clock className="w-4 h-4" />
              {activeTab === 'writeoff' && <span className="ml-2">{t('settings_page.writeoff_tab')}</span>}
            </TabsTrigger>
            <TabsTrigger value="system" className="flex-shrink-0">
              <SettingsIcon className="w-4 h-4" />
              {activeTab === 'system' && <span className="ml-2">{t('settings_page.system_tab')}</span>}
            </TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="automation">
          <Card>
            <CardHeader>
              <CardTitle>{t('settings_page.daily_digest_config')}</CardTitle>
              <CardDescription>{t('settings_page.automated_reminders')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>{t('settings_page.schedule_time')}</Label>
                <Input value="08:00" disabled className="h-12" />
                <p className="text-xs text-muted-foreground mt-1">{t('settings_page.jakarta_time_fixed')}</p>
              </div>
              <div>
                <Label>WhatsApp Gateway URL</Label>
                <Input value={process.env.REACT_APP_WHATSAPP_GATEWAY_URL || "http://dermapack.net:3001"} disabled className="h-12" />
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
        
        <TabsContent value="accident">
          <Card>
            <CardHeader>
              <CardTitle>Accident/Illness Follow-up Configuration</CardTitle>
              <CardDescription>Customize the follow-up schedule for hospital discharges</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {accidentFollowUp.map((stage, index) => (
                <div key={stage.stage} className="flex items-center gap-4 p-3 bg-muted/30 rounded">
                  <span className="font-medium w-32">{stage.name}</span>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      value={stage.days}
                      onChange={(e) => {
                        const updated = [...accidentFollowUp];
                        updated[index].days = parseInt(e.target.value);
                        setAccidentFollowUp(updated);
                      }}
                      className="w-20"
                    />
                    <span className="text-sm text-muted-foreground">days after discharge</span>
                  </div>
                </div>
              ))}
              <Button onClick={saveAccidentFollowUp} className="bg-teal-500 hover:bg-teal-600 text-white">
                Save Accident/Illness Follow-up Configuration
              </Button>
              <div className="p-4 bg-blue-50 rounded-lg mt-4">
                <p className="text-sm font-medium">🏥 Note:</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Changes will apply to NEW accident/illness events. Existing timelines remain unchanged.
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
                <Label>Disconnected Threshold (days since last contact)</Label>
                <Input
                  type="number"
                  value={inactiveDays}
                  onChange={(e) => setInactiveDays(parseInt(e.target.value))}
                  min="1"
                />
                <p className="text-xs text-muted-foreground">Default: 90 days. Members with no contact for this many days will show as "Disconnected"</p>
              </div>
              <Button onClick={saveEngagementSettings} className="bg-teal-500 hover:bg-teal-600 text-white">
                Save Engagement Thresholds
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="writeoff">
          <Card>
            <CardHeader>
              <CardTitle>Overdue Write-off Policy</CardTitle>
              <CardDescription>
                Configure how long overdue tasks remain visible before being auto-hidden.
                Set to 0 for tasks that should never be hidden.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="writeoff-birthday">Birthday (days)</Label>
                  <Input 
                    id="writeoff-birthday"
                    type="number" 
                    min="0"
                    max="365"
                    value={writeoffBirthday} 
                    onChange={(e) => setWriteoffBirthday(e.target.value)} 
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Default: 7 days. Birthday greetings older than this will be hidden.
                  </p>
                </div>
                
                <div>
                  <Label htmlFor="writeoff-grief">Grief Support (days)</Label>
                  <Input 
                    id="writeoff-grief"
                    type="number" 
                    min="0"
                    max="365"
                    value={writeoffGrief} 
                    onChange={(e) => setWriteoffGrief(e.target.value)} 
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Default: 14 days. Grief stages overdue by more than this will be hidden.
                  </p>
                </div>
                
                <div>
                  <Label htmlFor="writeoff-accident">Accident/Illness Recovery (days)</Label>
                  <Input 
                    id="writeoff-accident"
                    type="number" 
                    min="0"
                    max="365"
                    value={writeoffAccident} 
                    onChange={(e) => setWriteoffAccident(e.target.value)} 
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Default: 14 days. Accident follow-ups overdue by more than this will be hidden.
                  </p>
                </div>
                
                <div>
                  <Label htmlFor="writeoff-aid">Financial Aid (days)</Label>
                  <Input 
                    id="writeoff-aid"
                    type="number" 
                    min="0"
                    max="365"
                    value={writeoffFinancialAid} 
                    onChange={(e) => setWriteoffFinancialAid(e.target.value)} 
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Default: 0 (never hide). Set to 0 to always show overdue financial aid.
                  </p>
                </div>
              </div>
              
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h4 className="font-semibold text-sm mb-2">How Write-off Works:</h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• Tasks overdue beyond the threshold are <strong>automatically hidden</strong> from dashboard tabs</li>
                  <li>• Active overdue tasks can still be <strong>manually ignored</strong> using the "Ignore" button before auto write-off</li>
                  <li>• Set to <strong>0</strong> to never auto-hide (tasks stay visible until manually ignored)</li>
                  <li>• Ignored tasks remain visible in member profile history (greyed out)</li>
                  <li>• Write-off helps keep dashboard focused on actionable items</li>
                  <li>• <strong>Note:</strong> At-Risk and Disconnected status are open-ended (no write-off)</li>
                </ul>
              </div>
              
              <Button onClick={saveWriteoffSettings}>Save Write-off Settings</Button>
            </CardContent>
          </Card>
        </TabsContent>

        
        <TabsContent value="system">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Campus Timezone Configuration</CardTitle>
                <CardDescription>Set the timezone for date/time operations across the system</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="timezone">Campus Timezone</Label>
                  <Select value={campusTimezone} onValueChange={setCampusTimezone}>
                    <SelectTrigger id="timezone">
                      <SelectValue placeholder="Select timezone" />
                    </SelectTrigger>
                    <SelectContent className="max-h-[300px]">
                      {/* Asia Pacific */}
                      <SelectItem value="Asia/Jakarta">Asia/Jakarta (UTC+7) - Jakarta, Indonesia</SelectItem>
                      <SelectItem value="Asia/Singapore">Asia/Singapore (UTC+8) - Singapore</SelectItem>
                      <SelectItem value="Asia/Kuala_Lumpur">Asia/Kuala_Lumpur (UTC+8) - Kuala Lumpur, Malaysia</SelectItem>
                      <SelectItem value="Asia/Manila">Asia/Manila (UTC+8) - Manila, Philippines</SelectItem>
                      <SelectItem value="Asia/Bangkok">Asia/Bangkok (UTC+7) - Bangkok, Thailand</SelectItem>
                      <SelectItem value="Asia/Ho_Chi_Minh">Asia/Ho_Chi_Minh (UTC+7) - Ho Chi Minh, Vietnam</SelectItem>
                      <SelectItem value="Asia/Seoul">Asia/Seoul (UTC+9) - Seoul, South Korea</SelectItem>
                      <SelectItem value="Asia/Tokyo">Asia/Tokyo (UTC+9) - Tokyo, Japan</SelectItem>
                      <SelectItem value="Asia/Hong_Kong">Asia/Hong_Kong (UTC+8) - Hong Kong</SelectItem>
                      <SelectItem value="Asia/Shanghai">Asia/Shanghai (UTC+8) - Shanghai, China</SelectItem>
                      <SelectItem value="Asia/Taipei">Asia/Taipei (UTC+8) - Taipei, Taiwan</SelectItem>
                      <SelectItem value="Asia/Kolkata">Asia/Kolkata (UTC+5:30) - Mumbai, India</SelectItem>
                      <SelectItem value="Asia/Dubai">Asia/Dubai (UTC+4) - Dubai, UAE</SelectItem>
                      <SelectItem value="Asia/Riyadh">Asia/Riyadh (UTC+3) - Riyadh, Saudi Arabia</SelectItem>
                      
                      {/* Australia & Pacific */}
                      <SelectItem value="Australia/Sydney">Australia/Sydney (UTC+10/+11) - Sydney</SelectItem>
                      <SelectItem value="Australia/Melbourne">Australia/Melbourne (UTC+10/+11) - Melbourne</SelectItem>
                      <SelectItem value="Australia/Perth">Australia/Perth (UTC+8) - Perth</SelectItem>
                      <SelectItem value="Pacific/Auckland">Pacific/Auckland (UTC+12/+13) - Auckland, NZ</SelectItem>
                      <SelectItem value="Pacific/Fiji">Pacific/Fiji (UTC+12) - Fiji</SelectItem>
                      
                      {/* Americas */}
                      <SelectItem value="America/New_York">America/New_York (UTC-5/-4) - New York, USA</SelectItem>
                      <SelectItem value="America/Chicago">America/Chicago (UTC-6/-5) - Chicago, USA</SelectItem>
                      <SelectItem value="America/Denver">America/Denver (UTC-7/-6) - Denver, USA</SelectItem>
                      <SelectItem value="America/Los_Angeles">America/Los_Angeles (UTC-8/-7) - Los Angeles, USA</SelectItem>
                      <SelectItem value="America/Toronto">America/Toronto (UTC-5/-4) - Toronto, Canada</SelectItem>
                      <SelectItem value="America/Vancouver">America/Vancouver (UTC-8/-7) - Vancouver, Canada</SelectItem>
                      <SelectItem value="America/Mexico_City">America/Mexico_City (UTC-6) - Mexico City</SelectItem>
                      <SelectItem value="America/Sao_Paulo">America/Sao_Paulo (UTC-3) - São Paulo, Brazil</SelectItem>
                      <SelectItem value="America/Buenos_Aires">America/Buenos_Aires (UTC-3) - Buenos Aires, Argentina</SelectItem>
                      
                      {/* Europe */}
                      <SelectItem value="Europe/London">Europe/London (UTC+0/+1) - London, UK</SelectItem>
                      <SelectItem value="Europe/Paris">Europe/Paris (UTC+1/+2) - Paris, France</SelectItem>
                      <SelectItem value="Europe/Berlin">Europe/Berlin (UTC+1/+2) - Berlin, Germany</SelectItem>
                      <SelectItem value="Europe/Rome">Europe/Rome (UTC+1/+2) - Rome, Italy</SelectItem>
                      <SelectItem value="Europe/Madrid">Europe/Madrid (UTC+1/+2) - Madrid, Spain</SelectItem>
                      <SelectItem value="Europe/Amsterdam">Europe/Amsterdam (UTC+1/+2) - Amsterdam, Netherlands</SelectItem>
                      <SelectItem value="Europe/Moscow">Europe/Moscow (UTC+3) - Moscow, Russia</SelectItem>
                      <SelectItem value="Europe/Istanbul">Europe/Istanbul (UTC+3) - Istanbul, Turkey</SelectItem>
                      
                      {/* Africa */}
                      <SelectItem value="Africa/Cairo">Africa/Cairo (UTC+2) - Cairo, Egypt</SelectItem>
                      <SelectItem value="Africa/Johannesburg">Africa/Johannesburg (UTC+2) - Johannesburg, South Africa</SelectItem>
                      <SelectItem value="Africa/Lagos">Africa/Lagos (UTC+1) - Lagos, Nigeria</SelectItem>
                      <SelectItem value="Africa/Nairobi">Africa/Nairobi (UTC+3) - Nairobi, Kenya</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-2">
                    This timezone will be used for:
                  </p>
                  <ul className="text-xs text-muted-foreground mt-1 space-y-1 ml-4">
                    <li>• Daily reminder scheduling</li>
                    <li>• Birthday notifications</li>
                    <li>• Grief support timeline dates</li>
                    <li>• All date displays in the application</li>
                  </ul>
                </div>
                <Button onClick={saveTimezoneSettings}>Save Timezone Settings</Button>
              </CardContent>
            </Card>
            
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
                <Input value={campusCount.toString()} disabled />
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
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Settings;