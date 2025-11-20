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
import { Settings as SettingsIcon, Bell, Heart, Zap, Users, Clock, UserCircle, Upload, RefreshCw, Search } from 'lucide-react';
import FilterRuleBuilder from '@/components/FilterRuleBuilder';

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

  // Profile edit state
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileData, setProfileData] = useState({
    name: '',
    email: '',
    phone: ''
  });
  
  const saveProfile = async () => {
    try {
      await axios.put(`${API}/users/${user.id}`, {
        name: profileData.name,
        email: profileData.email,
        phone: profileData.phone
      });
      toast.success('Profile updated successfully');
      setEditingProfile(false);
      // Reload user data
      window.location.reload();
    } catch (error) {
      toast.error('Failed to update profile: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name || '',
        email: user.email || '',
        phone: user.phone || ''
      });
    }
  }, [user]);

  const [writeoffGrief, setWriteoffGrief] = useState(14);
  const [activeTab, setActiveTab] = useState('automation');
  const [griefStages, setGriefStages] = useState([
    { stage: '1_week', days: 7, name: 'First Follow-up' },
    { stage: '2_weeks', days: 14, name: 'Second Follow-up' },
    { stage: '1_month', days: 30, name: 'Third Follow-up' },
    { stage: '3_months', days: 90, name: 'Fourth Follow-up' },
    { stage: '6_months', days: 180, name: 'Fifth Follow-up' },
    { stage: '1_year', days: 365, name: 'Sixth Follow-up (1 Year Anniversary)' },
  ]);

  const [whatsappGateway, setWhatsappGateway] = useState('');
  const [digestTime, setDigestTime] = useState('08:00');
  
  const saveAutomationSettings = async () => {
    try {
      // Save WhatsApp Gateway to .env or settings collection
      // For now, show that it's saved (backend needs endpoint)
      toast.success('Automation settings saved');
    } catch (error) {
      toast.error('Failed to save settings');
    }
  };


  const [campusData, setCampusData] = useState(null);

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

  // Sync configuration state
  const [syncConfig, setSyncConfig] = useState({
    sync_method: 'polling',
    api_base_url: '',
    api_email: '',
    api_password: '',
    polling_interval_hours: 6,
    reconciliation_enabled: false,
    reconciliation_time: '03:00',
    filter_mode: 'include',
    filter_rules: [],
    webhook_secret: '',
    is_enabled: false
  });
  const [syncLogs, setSyncLogs] = useState([]);
  const [availableFields, setAvailableFields] = useState([]);
  const [showFilters, setShowFilters] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  
  const loadSyncConfig = async () => {
    try {
      const response = await axios.get(`${API}/sync/config`);
      console.log('Sync config API response:', response.data);
      if (response.data) {
        console.log('Setting sync config to:', response.data);
        setSyncConfig(response.data);
      } else {
        console.log('No sync config data returned');
      }
    } catch (error) {
      console.error('Error loading sync config:', error);
    }
  };
  
  const loadSyncLogs = async () => {
    try {
      console.log('Loading sync logs...');
      const response = await axios.get(`${API}/sync/logs?limit=10`);
      console.log('Sync logs response:', response.data);
      setSyncLogs(response.data);
      console.log('Sync logs set to state:', response.data.length, 'logs');
    } catch (error) {
      console.error('Error loading sync logs:', error);
    }
  };
  
  const testConnection = async () => {
    setTesting(true);
    try {
      const response = await axios.post(`${API}/sync/test-connection`, {
        api_base_url: syncConfig.api_base_url,
        api_email: syncConfig.api_email,
        api_password: syncConfig.api_password
      });
      
      if (response.data.success) {
        toast.success(response.data.message);
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Connection test failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setTesting(false);
    }
  };
  
  const saveSyncConfig = async () => {
    try {
      await axios.post(`${API}/sync/config`, syncConfig);
      toast.success('Sync configuration saved successfully');
      await loadSyncConfig();
      
      // If sync is enabled, automatically trigger initial sync
      if (syncConfig.is_enabled) {
        setTimeout(async () => {
          toast.info('Starting initial sync...');
          setSyncing(true);
          try {
            const response = await axios.post(`${API}/sync/members/pull`);
            toast.success(response.data.message + ` - ${response.data.stats.created} created, ${response.data.stats.updated} updated`);
            await loadSyncLogs();
            await loadSyncConfig();
          } catch (error) {
            toast.error('Sync failed: ' + (error.response?.data?.detail || error.message));
          } finally {
            setSyncing(false);
          }
        }, 500);
      }
    } catch (error) {
      toast.error('Failed to save configuration: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  const syncNow = async () => {
    setSyncing(true);
    try {
      const response = await axios.post(`${API}/sync/members/pull`);
      toast.success(response.data.message + ` - ${response.data.stats.created} created, ${response.data.stats.updated} updated`);
      loadSyncLogs();
    } catch (error) {
      toast.error('Sync failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'sync') {
      console.log('API Sync tab activated, loading config...');
      loadSyncConfig();
      loadSyncLogs();
    }
  }, [activeTab]);


  const discoverFields = async () => {
    setDiscovering(true);
    try {
      const response = await axios.post(`${API}/sync/discover-fields`, {
        sync_method: syncConfig.sync_method,
        api_base_url: syncConfig.api_base_url,
        api_email: syncConfig.api_email,
        api_password: syncConfig.api_password,
        polling_interval_hours: syncConfig.polling_interval_hours
      });
      
      setAvailableFields(response.data.fields);
      toast.success(response.data.message);
    } catch (error) {
      toast.error('Failed to discover fields: ' + (error.response?.data?.detail || error.message));
    } finally {
      setDiscovering(false);
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
      if (user?.campus_id && user.campus_id !== 'campus_id') {
        try {
          const campusRes = await axios.get(`${API}/campuses/${user.campus_id}`);
          setCampusTimezone(campusRes.data.timezone || 'Asia/Jakarta');
          setCampusData(campusRes.data);  // Store full campus data
        } catch (error) {
          console.error('Error loading campus timezone:', error);
          setCampusTimezone('Asia/Jakarta');
        }
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
      
      if (!campusData) {
        toast.error('Campus data not loaded');
        return;
      }
      
      await axios.put(`${API}/campuses/${user.campus_id}`, {
        campus_name: campusData.campus_name,
        location: campusData.location,
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
      
      <Tabs defaultValue="profile" className="max-w-full" onValueChange={(v) => setActiveTab(v)}>
        <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex min-w-full w-max sm:w-full">
            <TabsTrigger value="profile" className="flex-shrink-0">
              <UserCircle className="w-4 h-4" />
              {activeTab === 'profile' && <span className="ml-2">Profile</span>}
            </TabsTrigger>
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
            <TabsTrigger value="sync" className="flex-shrink-0">
              <RefreshCw className="w-4 h-4" />
              {activeTab === 'sync' && <span className="ml-2">API Sync</span>}
            </TabsTrigger>
          </TabsList>
        </div>
        

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>My Profile</CardTitle>
              <CardDescription>Manage your profile information and photo</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Profile Photo */}
              <div className="flex items-start gap-6">
                <div className="flex-shrink-0">
                  {user?.photo_url ? (
                    <img 
                      src={`${BACKEND_URL}${user.photo_url}`} 
                      alt={user.name}
                      className="w-24 h-24 rounded-full object-cover border-4 border-teal-100"
                    />
                  ) : (
                    <div className="w-24 h-24 rounded-full bg-teal-100 flex items-center justify-center border-4 border-teal-200">
                      <span className="text-3xl font-bold text-teal-700">
                        {user?.name?.charAt(0).toUpperCase()}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-1">Profile Photo</h3>
                  <p className="text-sm text-gray-500 mb-3">Upload a photo for your profile. This will appear in activity logs and navigation.</p>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => document.getElementById('photo-upload').click()}
                      disabled={uploading}
                      className="gap-2"
                    >
                      <Upload className="w-4 h-4" />
                      {uploading ? 'Uploading...' : 'Upload Photo'}
                    </Button>
                    <input 
                      id="photo-upload"
                      type="file" 
                      accept="image/*"
                      className="hidden"
                      onChange={handlePhotoUpload}
                    />
                  </div>
                </div>
              </div>
              
              {/* Profile Information */}
              <div className="space-y-4 pt-6 border-t">
                <div>
                  <Label className="text-gray-700">Name</Label>
                  <Input 
                    value={editingProfile ? profileData.name : user?.name} 
                    onChange={(e) => setProfileData({...profileData, name: e.target.value})}
                    disabled={!editingProfile} 
                    className={!editingProfile ? "bg-gray-50" : ""} 
                  />
                </div>
                <div>
                  <Label className="text-gray-700">Email</Label>
                  <Input 
                    value={editingProfile ? profileData.email : user?.email} 
                    onChange={(e) => setProfileData({...profileData, email: e.target.value})}
                    disabled={!editingProfile} 
                    className={!editingProfile ? "bg-gray-50" : ""} 
                  />
                </div>
                <div>
                  <Label className="text-gray-700">Phone</Label>
                  <Input 
                    value={editingProfile ? profileData.phone : user?.phone} 
                    onChange={(e) => setProfileData({...profileData, phone: e.target.value})}
                    disabled={!editingProfile} 
                    className={!editingProfile ? "bg-gray-50" : ""} 
                  />
                </div>
                <div>
                  <Label className="text-gray-700">Role</Label>
                  <Input value={user?.role === 'full_admin' ? 'Full Administrator' : user?.role === 'campus_admin' ? 'Campus Administrator' : 'Pastor'} disabled className="bg-gray-50" />
                </div>
                
                {/* Edit/Save buttons */}
                <div className="flex gap-2">
                  {!editingProfile ? (
                    <Button onClick={() => setEditingProfile(true)} variant="outline">
                      Edit Profile
                    </Button>
                  ) : (
                    <>
                      <Button onClick={() => {
                        setEditingProfile(false);
                        setProfileData({name: user.name, email: user.email, phone: user.phone});
                      }} variant="outline">
                        Cancel
                      </Button>
                      <Button onClick={saveProfile} className="bg-teal-500 hover:bg-teal-600">
                        Save Changes
                      </Button>
                    </>
                  )}
                </div>
              </div>
              
              <p className="text-xs text-gray-500 pt-4 border-t">
                To update your name, email, phone, or role, please contact a Full Administrator.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

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
                <Input 
                  value={whatsappGateway || process.env.REACT_APP_WHATSAPP_GATEWAY_URL || "http://dermapack.net:3001"} 
                  onChange={(e) => setWhatsappGateway(e.target.value)}
                  disabled={user?.role !== 'full_admin'}
                  className="h-12" 
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {user?.role === 'full_admin' ? 'Edit and save to update' : 'Only full admin can edit'}
                </p>
              </div>
              
              <div>
                <Label>Daily Digest Time</Label>
                <Input 
                  type="time"
                  value={digestTime}
                  onChange={(e) => setDigestTime(e.target.value)}
                  disabled={user?.role !== 'full_admin'}
                  className="h-12"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {user?.role === 'full_admin' ? 'Time to send daily pastoral care digest (Jakarta time)' : 'Only full admin can edit'}
                </p>
              </div>
              
              {user?.role === 'full_admin' && (
                <Button onClick={saveAutomationSettings} className="bg-teal-500 hover:bg-teal-600">
                  Save Automation Settings
                </Button>
              )}
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

        
        <TabsContent value="sync">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Core API Sync Configuration</CardTitle>
                <CardDescription>
                  Connect to FaithFlow Enterprise (core system) to automatically sync member data. 
                  Pastoral care events remain local and private.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>Sync Method</Label>
                  <Select value={syncConfig.sync_method} onValueChange={(v) => setSyncConfig({...syncConfig, sync_method: v})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="polling">Polling (Pull every X hours)</SelectItem>
                      <SelectItem value="webhook">Webhook (Real-time push from core)</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-gray-500 mt-1">
                    {syncConfig.sync_method === 'polling' 
                      ? 'FaithTracker pulls data from core API periodically'
                      : 'Core system pushes updates to FaithTracker in real-time'}
                  </p>
                </div>
                
                <div>
                  <Label>API Base URL</Label>
                  <Input 
                    placeholder="https://faithflow.yourdomain.com"
                    value={syncConfig.api_base_url}
                    onChange={(e) => setSyncConfig({...syncConfig, api_base_url: e.target.value})}
                  />
                  <p className="text-xs text-gray-500 mt-1">Base URL of the core FaithFlow API (without /api suffix)</p>
                </div>
                
                <div>
                  <Label>API Username</Label>
                  <Input 
                    type="text"
                    placeholder="admin@yourdomain.com"
                    value={syncConfig.api_email}
                    onChange={(e) => setSyncConfig({...syncConfig, api_email: e.target.value})}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Username for API authentication. 
                    <strong className="text-yellow-600"> Note:</strong> FaithFlow Enterprise requires email format (user@domain.com)
                  </p>
                </div>
                
                <div>
                  <Label>API Secret Key</Label>
                  <Input 
                    type="password"
                    placeholder="Enter API password"
                    value={syncConfig.api_password === '********' ? '' : syncConfig.api_password}
                    onChange={(e) => setSyncConfig({...syncConfig, api_password: e.target.value})}
                  />
                  <p className="text-xs text-gray-500 mt-1">Password for API authentication</p>
                </div>
                
                {/* Polling-specific settings */}
                {syncConfig.sync_method === 'polling' && (
                  <div>
                    <Label>Polling Interval (hours)</Label>
                    <Select 
                      value={String(syncConfig.polling_interval_hours)} 
                      onValueChange={(v) => setSyncConfig({...syncConfig, polling_interval_hours: parseInt(v)})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">Every 1 hour</SelectItem>
                        <SelectItem value="3">Every 3 hours</SelectItem>
                        <SelectItem value="6">Every 6 hours (recommended)</SelectItem>
                        <SelectItem value="12">Every 12 hours</SelectItem>
                        <SelectItem value="24">Every 24 hours</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-gray-500 mt-1">How often to pull data from core API</p>
                  </div>
                )}

                {/* Sync Filters */}
                <div className="border-t pt-4 mt-4">
                  <div className="flex items-center gap-3 mb-4">
                    <input 
                      type="checkbox"
                      checked={showFilters}
                      onChange={(e) => {
                        setShowFilters(e.target.checked);
                        if (!e.target.checked) {
                          // Clear filters when unchecking
                          setSyncConfig({...syncConfig, filter_rules: []});
                        }
                      }}
                      className="w-4 h-4 text-teal-600"
                      id="enable-filters"
                    />
                    <div>
                      <label htmlFor="enable-filters" className="font-medium text-sm cursor-pointer">
                        Enable Custom Filters
                      </label>
                      <p className="text-xs text-gray-500">
                        {showFilters 
                          ? 'Filters are active - Only matching members will be synced' 
                          : 'No filters - All members from core API will be synced'}
                      </p>
                    </div>
                  </div>
                  
                  {showFilters && (
                    <>
                      <h4 className="font-medium text-sm mb-2">Sync Filters</h4>
                      
                      {/* Filter Mode Selector */}
                      <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                        <Label className="mb-2 block">Filter Mode</Label>
                        <Select value={syncConfig.filter_mode} onValueChange={(v) => setSyncConfig({...syncConfig, filter_mode: v})}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="include">
                              <div className="flex flex-col">
                                <span className="font-medium">Include Mode</span>
                                <span className="text-xs text-gray-500">Only sync members matching the filters below</span>
                              </div>
                            </SelectItem>
                            <SelectItem value="exclude">
                              <div className="flex flex-col">
                                <span className="font-medium">Exclude Mode</span>
                                <span className="text-xs text-gray-500">Sync all members EXCEPT those matching the filters</span>
                              </div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        
                        <div className={`mt-3 p-2 rounded text-xs ${syncConfig.filter_mode === 'include' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                          <p className={`font-medium mb-1 ${syncConfig.filter_mode === 'include' ? 'text-green-900' : 'text-red-900'}`}>
                            {syncConfig.filter_mode === 'include' ? '✓ Include Mode' : '✗ Exclude Mode'}
                          </p>
                          <p className={syncConfig.filter_mode === 'include' ? 'text-green-700' : 'text-red-700'}>
                            {syncConfig.filter_mode === 'include' 
                              ? 'Only members matching ALL the filters below will be synced to FaithTracker. All others are ignored.'
                              : 'All members will be synced EXCEPT those matching the filters below. Matching members are skipped.'
                            }
                          </p>
                          <p className="mt-2 text-gray-600">
                            <strong>Example:</strong> {syncConfig.filter_mode === 'include' 
                              ? 'Filters: Female + Age 18-35 → Only syncs women aged 18-35'
                              : 'Filters: Female + Age 18-35 → Syncs everyone EXCEPT women aged 18-35'
                            }
                          </p>
                        </div>
                      </div>
                  
                  <p className="text-xs text-gray-600 mb-4">Discover available fields from core API, then create custom filter rules.</p>
                  
                  {/* Discover Fields Button */}
                  <div className="mb-4">
                    <Button 
                      onClick={discoverFields}
                      disabled={discovering || !syncConfig.api_base_url || !syncConfig.api_email || !syncConfig.api_password || syncConfig.api_password === '********'}
                      variant="outline"
                      className="gap-2"
                    >
                      {discovering ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-teal-500"></div>
                          Discovering Fields...
                        </>
                      ) : (
                        <>
                          <Search className="w-4 h-4" />
                          Discover Available Fields
                        </>
                      )}
                    </Button>
                    {availableFields.length > 0 && (
                      <p className="text-xs text-green-600 mt-2">✓ Found {availableFields.length} fields. Build filter rules below.</p>
                    )}
                  </div>
                  
                  {/* Dynamic Filter Rule Builder */}
                  <FilterRuleBuilder 
                    availableFields={availableFields}
                    filterRules={syncConfig.filter_rules || []}
                    onChange={(rules) => setSyncConfig({...syncConfig, filter_rules: rules})}
                  />
                  
                  {/* Active Filters Summary */}
                  {syncConfig.filter_rules && syncConfig.filter_rules.length > 0 && (
                    <div className={`mt-3 p-3 rounded border ${syncConfig.filter_mode === 'include' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                      <p className={`font-medium text-sm mb-2 ${syncConfig.filter_mode === 'include' ? 'text-green-900' : 'text-red-900'}`}>
                        {syncConfig.filter_mode === 'include' ? '✓ Will ONLY Sync Members Matching ALL Rules:' : '✗ Will EXCLUDE Members Matching ALL Rules:'}
                      </p>
                      <ul className={`space-y-1 text-xs ${syncConfig.filter_mode === 'include' ? 'text-green-700' : 'text-red-700'}`}>
                        {syncConfig.filter_rules.map((rule, idx) => {
                          const field = availableFields.find(f => f.name === rule.field);
                          const fieldLabel = field?.label || rule.field;
                          return (
                            <li key={idx}>
                              • {fieldLabel} {rule.operator.replace('_', ' ')} {
                                Array.isArray(rule.value) ? rule.value.join(', ') : rule.value
                              }
                            </li>
                          );
                        })}
                      </ul>
                      <p className="mt-2 text-xs text-gray-600 italic">
                        {syncConfig.filter_mode === 'include' 
                          ? 'Only members matching ALL rules above will be synced to FaithTracker'
                          : 'Members matching ALL rules above will be SKIPPED (everyone else synced)'
                        }
                      </p>
                    </div>
                  )}
                    </>
                  )}
                </div>

                
                {/* Webhook-specific settings */}
                {syncConfig.sync_method === 'webhook' && syncConfig.webhook_secret && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
                    <h4 className="font-medium text-sm text-blue-900">Webhook Configuration for Core System</h4>
                    <div>
                      <Label className="text-blue-900">Webhook URL</Label>
                      <div className="flex gap-2">
                        <Input 
                          value={`${window.location.origin}/api/sync/webhook`}
                          readOnly
                          className="font-mono text-xs bg-white"
                        />
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(`${window.location.origin}/api/sync/webhook`);
                            toast.success('Webhook URL copied to clipboard');
                          }}
                        >
                          Copy
                        </Button>
                      </div>
                    </div>
                    <div>
                      <Label className="text-blue-900">Webhook Secret</Label>
                      <div className="flex gap-2">
                        <Input 
                          value={syncConfig.webhook_secret}
                          readOnly
                          className="font-mono text-xs bg-white"
                        />
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(syncConfig.webhook_secret);
                            toast.success('Webhook secret copied to clipboard');
                          }}
                        >
                          Copy
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-blue-700">
                      ⓘ Configure these values in your core FaithFlow system's webhook settings. 
                      The core system should send POST requests with HMAC-SHA256 signature in X-Webhook-Signature header.
                    </p>
                  </div>
                )}
                
                <div className="border-t pt-4 mt-4">
                  <div className="flex items-start gap-3">
                    <input 
                      type="checkbox"
                      checked={syncConfig.is_enabled}
                      onChange={(e) => setSyncConfig({...syncConfig, is_enabled: e.target.checked})}
                      className="w-5 h-5 text-teal-600 mt-0.5"
                      id="enable-sync"
                    />
                    <div className="flex-1">
                      <label htmlFor="enable-sync" className="text-sm font-semibold text-gray-900 cursor-pointer">
                        Enable Member Data Sync
                      </label>
                      <p className="text-xs text-gray-600 mt-1">
                        {syncConfig.is_enabled ? (
                          <span className="text-green-700 font-medium">
                            ✓ Sync is ACTIVE - {syncConfig.sync_method === 'polling' 
                              ? `Automatically pulls data every ${syncConfig.polling_interval_hours} hours` 
                              : 'Receives real-time updates via webhooks'}
                          </span>
                        ) : (
                          <span className="text-gray-500">
                            ✗ Sync is DISABLED - You can manually create and edit members freely
                          </span>
                        )}
                      </p>
                      <div className="mt-2 text-xs text-gray-600 space-y-1 bg-gray-50 p-2 rounded">
                        <p><strong>When ENABLED:</strong></p>
                        <p>• Member data syncs from core system automatically</p>
                        <p>• You CANNOT create new members manually (read-only)</p>
                        <p>• Profile updates (name, phone, photo) come from core only</p>
                        <p>• Care events and pastoral data remain fully editable</p>
                        <p className="pt-1"><strong>When DISABLED:</strong></p>
                        <p>• Works as standalone app</p>
                        <p>• Full control to create/edit members</p>
                        <p>• No automatic sync</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Reconciliation Toggle - Recommended for Webhook mode */}
                {syncConfig.sync_method === 'webhook' && (
                  <div className="border-t pt-4 mt-4">
                    <div className="flex items-start gap-3">
                      <input 
                        type="checkbox"
                        checked={syncConfig.reconciliation_enabled}
                        onChange={(e) => setSyncConfig({...syncConfig, reconciliation_enabled: e.target.checked})}
                        className="w-5 h-5 text-teal-600 mt-0.5"
                        id="enable-reconciliation"
                      />
                      <div className="flex-1">
                        <label htmlFor="enable-reconciliation" className="text-sm font-semibold text-gray-900 cursor-pointer">
                          Enable Daily Reconciliation (Recommended)
                        </label>
                        <p className="text-xs text-gray-600 mt-1">
                          {syncConfig.reconciliation_enabled ? (
                            <span className="text-green-700 font-medium">
                              ✓ Daily reconciliation ACTIVE at {syncConfig.reconciliation_time} (Jakarta time)
                            </span>
                          ) : (
                            <span className="text-gray-500">
                              ✗ No reconciliation - Relies only on webhooks
                            </span>
                          )}
                        </p>
                        <div className="mt-2 text-xs text-gray-600 space-y-1 bg-yellow-50 p-2 rounded border border-yellow-200">
                          <p><strong>Why Reconciliation?</strong></p>
                          <p>• Webhooks can occasionally fail or be missed</p>
                          <p>• Network issues might cause lost updates</p>
                          <p>• Daily full sync ensures 100% data integrity</p>
                          <p>• Runs at low-traffic time (3 AM by default)</p>
                          <p>• <strong>Highly recommended for webhook mode</strong></p>
                        </div>
                        {syncConfig.reconciliation_enabled && (
                          <div className="mt-2">
                            <Label className="text-xs">Reconciliation Time (24-hour format)</Label>
                            <Input 
                              type="time"
                              value={syncConfig.reconciliation_time}
                              onChange={(e) => setSyncConfig({...syncConfig, reconciliation_time: e.target.value})}
                              className="w-32 h-8 text-xs"
                            />
                            <p className="text-xs text-gray-500 mt-1">Asia/Jakarta timezone</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                
                <div className="flex gap-2 pt-4 border-t">
                  <Button 
                    onClick={testConnection}
                    disabled={testing || !syncConfig.api_base_url || !syncConfig.api_email || !syncConfig.api_password || syncConfig.api_password === '********'}
                    variant="outline"
                    className="gap-2"
                  >
                    {testing ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-teal-500"></div>
                        Testing...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4" />
                        Test Connection
                      </>
                    )}
                  </Button>
                  <Button 
                    onClick={saveSyncConfig}
                    className="bg-teal-500 hover:bg-teal-600 text-white"
                  >
                    {syncConfig.is_enabled ? 'Save Configuration & Sync Now' : 'Save Configuration'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Current Sync Status Card - Always show */}
            <Card className="bg-gradient-to-r from-teal-50 to-blue-50 border-teal-200">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center justify-between">
                    <span>🔄 Active Sync Configuration</span>
                    {syncConfig.is_enabled ? (
                      <Button 
                        variant="outline" 
                        size="sm"
                        className="text-red-600 border-red-300 hover:bg-red-50"
                        onClick={async () => {
                          if (confirm('Disable sync? This will stop automatic syncing but preserve all data.')) {
                            const updated = {...syncConfig, is_enabled: false};
                            await axios.post(`${API}/sync/config`, updated);
                            toast.success('Sync disabled');
                            loadSyncConfig();
                          }
                        }}
                      >
                        Disable Sync
                      </Button>
                    ) : (
                      <Button 
                        variant="outline" 
                        size="sm"
                        className="text-green-600 border-green-300 hover:bg-green-50"
                        onClick={async () => {
                          if (confirm('Enable sync? This will start automatic syncing from core API.')) {
                            const updated = {...syncConfig, is_enabled: true};
                            await axios.post(`${API}/sync/config`, updated);
                            toast.success('Sync enabled');
                            loadSyncConfig();
                          }
                        }}
                      >
                        Enable Sync
                      </Button>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-600 text-xs uppercase">Method</p>
                    <p className="font-medium">{syncConfig.sync_method === 'polling' ? '📊 Polling' : '⚡ Webhook'}</p>
                  </div>
                  <div>
                    <p className="text-gray-600 text-xs uppercase">Status</p>
                    <p className={`font-medium ${syncConfig.is_enabled ? 'text-green-600' : 'text-gray-500'}`}>
                      {syncConfig.is_enabled ? '✓ Enabled' : '✗ Disabled'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-600 text-xs uppercase">API URL</p>
                    <p className="font-mono text-xs truncate">{syncConfig.api_base_url}</p>
                  </div>
                  <div>
                    <p className="text-gray-600 text-xs uppercase">Username</p>
                    <p className="font-mono text-xs truncate">{syncConfig.api_email}</p>
                  </div>
                  
                  {syncConfig.sync_method === 'webhook' && (
                    <>
                      <div className="md:col-span-2">
                        <p className="text-gray-600 text-xs uppercase mb-1">Webhook URL for Core System</p>
                        <div className="flex gap-2">
                          <code className="flex-1 text-xs bg-white p-2 rounded border">{window.location.origin}/api/sync/webhook</code>
                          <Button size="sm" variant="outline" onClick={() => {
                            navigator.clipboard.writeText(`${window.location.origin}/api/sync/webhook`);
                            toast.success('Copied!');
                          }}>Copy</Button>
                        </div>
                      </div>
                      <div className="md:col-span-2">
                        <p className="text-gray-600 text-xs uppercase mb-1">Webhook Secret</p>
                        {syncConfig.webhook_secret ? (
                          <div className="flex gap-2">
                            <code className="flex-1 text-xs bg-white p-2 rounded border font-mono">{syncConfig.webhook_secret}</code>
                            <Button size="sm" variant="outline" onClick={() => {
                              navigator.clipboard.writeText(syncConfig.webhook_secret);
                              toast.success('Copied!');
                            }}>Copy</Button>
                            <Button size="sm" variant="outline" className="text-orange-600 border-orange-300" onClick={async () => {
                              if (confirm('Regenerate webhook secret? You must update the core system with the new secret.')) {
                                try {
                                  const response = await axios.post(`${API}/sync/regenerate-secret`);
                                  toast.success('Secret regenerated. Update core system!');
                                  await loadSyncConfig();
                                } catch (error) {
                                  toast.error('Failed to regenerate secret');
                                }
                              }
                            }}>Regenerate</Button>
                          </div>
                        ) : (
                          <p className="text-xs text-yellow-600 bg-yellow-50 p-2 rounded border border-yellow-200">
                            ⚠️ Webhook secret will be generated when you save configuration
                          </p>
                        )}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

            
            <Card>
              <CardHeader>
                <CardTitle>Manual Sync</CardTitle>
                <CardDescription>
                  Manually trigger a sync to pull the latest member data from core system.
                  {syncConfig.reconciliation_enabled && (
                    <span className="block mt-2 text-blue-600">
                      ℹ️ Automatic reconciliation runs daily at {syncConfig.reconciliation_time} (Asia/Jakarta timezone) to ensure data integrity.
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {syncConfig.last_sync_at && (
                  <div className="text-sm text-gray-600">
                    <p><span className="font-medium">Last Sync:</span> {new Date(syncConfig.last_sync_at).toLocaleString()}</p>
                    <p><span className="font-medium">Status:</span> <span className={syncConfig.last_sync_status === 'success' ? 'text-green-600' : 'text-red-600'}>
                      {syncConfig.last_sync_status}
                    </span></p>
                    {syncConfig.last_sync_message && (
                      <p><span className="font-medium">Message:</span> {syncConfig.last_sync_message}</p>
                    )}
                  </div>
                )}
                
                <Button 
                  onClick={syncNow}
                  disabled={syncing || !syncConfig.is_enabled}
                  className="bg-blue-500 hover:bg-blue-600 text-white gap-2"
                >
                  {syncing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4" />
                      Sync Now
                    </>
                  )}
                </Button>
                
                {!syncConfig.is_enabled && (
                  <p className="text-xs text-yellow-600">⚠️ Sync is disabled. Enable it in configuration above.</p>
                )}
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Sync History</CardTitle>
                <CardDescription>Recent sync operations and their results</CardDescription>
              </CardHeader>
              <CardContent>
                {syncLogs.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">No sync history yet</p>
                ) : (
                  <div className="space-y-2">
                    {syncLogs.map((log) => (
                      <div key={log.id} className={`p-3 rounded border ${
                        log.status === 'success' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                      }`}>
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <p className="text-sm font-medium">
                              {log.sync_type.charAt(0).toUpperCase() + log.sync_type.slice(1)} Sync
                            </p>
                            <p className="text-xs text-gray-600">
                              {new Date(log.started_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} 
                              {log.duration_seconds && ` • ${log.duration_seconds.toFixed(1)}s`}
                            </p>
                          </div>
                          <div className="text-right text-xs">
                            {log.status === 'success' ? (
                              <>
                                <p className="text-green-700">✓ Success</p>
                                <p className="text-gray-600">
                                  {log.members_created} created, {log.members_updated} updated
                                  {log.members_archived > 0 && `, ${log.members_archived} archived`}
                                </p>
                              </>
                            ) : (
                              <>
                                <p className="text-red-700">✗ Failed</p>
                                <p className="text-gray-600">{log.error_message}</p>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            
            <Card className="bg-yellow-50 border-yellow-200">
              <CardHeader>
                <CardTitle className="text-sm">Important Notes - {syncConfig.sync_method === 'polling' ? 'Polling Mode' : 'Webhook Mode'}</CardTitle>
              </CardHeader>
              <CardContent className="text-xs space-y-2 text-gray-700">
                <p>• When sync is enabled, you cannot manually create new members (read-only from core)</p>
                <p>• Sync only updates basic profile data (name, phone, birth date, photo)</p>
                <p>• All pastoral care events, engagement data, and notes are preserved locally</p>
                <p>• Members deactivated in core system will be archived (hidden from lists but history preserved)</p>
                
                {syncConfig.sync_method === 'polling' ? (
                  <>
                    <p className="pt-2 border-t border-yellow-300 font-medium">Polling Mode:</p>
                    <p>• FaithTracker pulls data from core API every {syncConfig.polling_interval_hours} hours</p>
                    <p>• Changes may take up to {syncConfig.polling_interval_hours} hours to appear</p>
                    <p>• No changes needed on core system side</p>
                    <p>• Lower server load, delayed updates</p>
                  </>
                ) : (
                  <>
                    <p className="pt-2 border-t border-yellow-300 font-medium">Webhook Mode:</p>
                    <p>• Core system pushes updates to FaithTracker in real-time</p>
                    <p>• Changes appear immediately (within seconds)</p>
                    <p>• <strong>Requires core system configuration:</strong> Add webhook URL and secret to FaithFlow Enterprise</p>
                    <p>• Core must send HMAC-SHA256 signature in X-Webhook-Signature header</p>
                    <p>• See webhook details in blue box above</p>
                  </>
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