/**
 * Dashboard Page - Main task-oriented interface
 * Displays today's tasks, overdue items, and upcoming events
 * Uses React Query for optimized data fetching and caching
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/context/AuthContext';
import LazyImage from '@/components/LazyImage';
import { MemberAvatar } from '@/components/MemberAvatar';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { format as formatDateFns } from 'date-fns';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar as CalendarComponent } from '@/components/ui/calendar';
import { Heart, Users, Hospital, Calendar, AlertTriangle, DollarSign, Bell, Plus, Check, MoreVertical, Phone, Cake, CalendarIcon } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatDate = (dateStr, format = 'short') => {
  try {
    if (format === 'dd MMM yyyy') {
      return new Date(dateStr).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
    }
    return new Date(dateStr).toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
  } catch { return dateStr; }
};

const getRelativeDate = (dateStr) => {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffTime = now - date;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return '1 day ago';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) {
      const weeks = Math.floor(diffDays / 7);
      return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`;
    }
    const months = Math.floor(diffDays / 30);
    return months === 1 ? '1 month ago' : `${months} months ago`;
  } catch {
    return dateStr;
  }
};

const getGriefStageBadge = (stage) => {
  const badges = {
    '1_week': 'Week 1',
    '2_weeks': 'Week 2',
    '1_month': 'Month 1',
    '3_months': 'Month 3',
    '6_months': 'Month 6',
    '1_year': 'Year 1'
  };
  return badges[stage] || stage.replace('_', ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
};

const getAccidentStageBadge = (stage) => {
  const badges = {
    'first_followup': 'First Follow-up',
    'second_followup': 'Second Follow-up',
    'third_followup': 'Third Follow-up',
    'final_check': 'Final Check'
  };
  return badges[stage] || stage.replace('_', ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
};

const triggerHaptic = () => {
  if ('vibrate' in navigator) {
    navigator.vibrate(50); // 50ms vibration
  }
};

const MemberNameWithAvatar = ({ member, memberId }) => {
  const getInitials = (name) => {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return parts[0][0] + parts[parts.length - 1][0];
    }
    return name.substring(0, 2);
  };

  const photoUrl = member?.photo_url ? `${BACKEND_URL}/api${member.photo_url}` : null;

  return (
    <Link to={`/members/${memberId}`} className="flex items-center gap-3 hover:text-teal-700">
      <div className="w-10 h-10 rounded-full overflow-hidden bg-teal-100 flex items-center justify-center">
        {photoUrl ? (
          <LazyImage 
            src={photoUrl} 
            alt={member.name}
            className="w-full h-full object-cover"
            placeholderClassName="w-full h-full bg-teal-100 flex items-center justify-center text-teal-700 text-xs font-semibold"
          />
        ) : (
          <span className="text-teal-700 font-semibold text-xs">
            {getInitials(member.name)}
          </span>
        )}
      </div>
      <div>
        <p className="font-semibold hover:underline">{member.name}</p>
      </div>
    </Link>
  );
};

const formatPhoneForWhatsApp = (phone) => {
  if (!phone) return '#';
  let formatted = phone;
  if (formatted.startsWith('0')) {
    formatted = '62' + formatted.substring(1);
  } else if (formatted.startsWith('+')) {
    formatted = formatted.substring(1);
  }
  return `https://wa.me/${formatted}`;
};

const markBirthdayComplete = async (eventId, queryClient, t) => {
  try {
    // Optimistic update - remove from UI immediately
    queryClient.setQueryData(['dashboard'], (old) => {
      if (!old) return old;
      return {
        ...old,
        today: old.today.filter(e => e.id !== eventId),
        overdue: old.overdue.filter(e => e.id !== eventId)
      };
    });
    
    await axios.post(`${API}/care-events/${eventId}/complete`);
    toast.success(t('toasts.birthday_completed'));
    // Refetch to get accurate data
    await queryClient.invalidateQueries(['dashboard']);
  } catch (error) {
    toast.error(t('toasts.failed_complete'));
    // Revert optimistic update on error
    queryClient.invalidateQueries(['dashboard']);
  }
};

const markGriefStageComplete = async (stageId, queryClient, t) => {
  try {
    // Optimistic update
    queryClient.setQueryData(['dashboard'], (old) => {
      if (!old) return old;
      return {
        ...old,
        today: old.today.filter(e => e.id !== stageId),
        overdue: old.overdue.filter(e => e.id !== stageId),
        upcoming: old.upcoming.filter(e => e.id !== stageId)
      };
    });
    
    await axios.post(`${API}/grief-support/${stageId}/complete`);
    toast.success(t('toasts.grief_completed'));
    await queryClient.invalidateQueries(['dashboard']);
  } catch (error) {
    toast.error(t('toasts.failed_complete'));
    queryClient.invalidateQueries(['dashboard']);
  }
};

const markAccidentComplete = async (eventId, queryClient, t) => {
  try {
    await axios.post(`${API}/care-events/${eventId}/complete`);
    toast.success(t('toasts.accident_completed'));
    // Invalidate and refetch dashboard data
    await queryClient.invalidateQueries(['dashboard']);
  } catch (error) {
    toast.error(t('toasts.failed_complete'));
  }
};

const markMemberContacted = async (memberId, memberName, user, queryClient, t) => {
  try {
    // Create a regular contact event which updates last_contact_date
    const response = await axios.post(`${API}/care-events`, {
      member_id: memberId,
      campus_id: user?.campus_id || '2b3f9094-eef4-4af4-a3ff-730ef4adeb8a',
      event_type: 'regular_contact',
      event_date: new Date().toISOString().split('T')[0],
      title: `Contact with ${memberName}`,
      description: 'Contacted member - marked from dashboard',
      completed: true
    });
    
    // If the event was created, mark it as completed to trigger activity logging
    if (response.data && response.data.id) {
      await axios.post(`${API}/care-events/${response.data.id}/complete`);
    }
    
    toast.success(t('toasts.member_contacted', {name: memberName}));
    // Invalidate and refetch dashboard data
    await queryClient.invalidateQueries(['dashboard']);
  } catch (error) {
    toast.error('Failed to mark as contacted');
    console.error('Error marking member contacted:', error);
  }
};

export const Dashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  
  // React Query for dashboard data
  const { data: dashboardData, isLoading, refetch: refetchDashboard } = useQuery({
    queryKey: ['dashboard', 'reminders', user?.campus_id],
    queryFn: async () => {
      const response = await axios.get(`${API}/dashboard/reminders`, {
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        },
        params: {
          t: Date.now()
        }
      });
      return response.data;
    },
    enabled: !!user?.campus_id,
    staleTime: 1000 * 30, // 30 seconds
  });
  
  // React Query for all members (for quick event form)
  const { data: allMembers = [] } = useQuery({
    queryKey: ['members', 'all'],
    queryFn: async () => {
      const response = await axios.get(`${API}/members?limit=1000`);
      return response.data;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes (member list changes infrequently)
  });
  
  // Extract data with defaults
  const birthdaysToday = dashboardData?.birthdays_today || [];
  const overdueBirthdays = dashboardData?.overdue_birthdays || [];
  const todayTasks = dashboardData?.today_tasks || [];
  const griefDue = dashboardData?.grief_today || [];
  const griefToday = dashboardData?.grief_today || [];
  const accidentFollowUp = dashboardData?.accident_followup || [];
  const hospitalFollowUp = [];
  const atRiskMembers = dashboardData?.at_risk_members || [];
  const disconnectedMembers = dashboardData?.disconnected_members || [];
  const upcomingBirthdays = dashboardData?.upcoming_birthdays || [];
  const upcomingTasks = dashboardData?.upcoming_tasks || [];
  const financialAidDue = dashboardData?.financial_aid_due || [];
  const suggestions = dashboardData?.ai_suggestions || [];
  
  // UI state (not related to server data)
  const [quickEventOpen, setQuickEventOpen] = useState(false);
  const [eventDateOpen, setEventDateOpen] = useState(false);
  const [paymentDateOpen, setPaymentDateOpen] = useState(false);
  const [endDateOpen, setEndDateOpen] = useState(false);
  const [activeOverdueTab, setActiveOverdueTab] = useState('birthdays');
  const [selectedMemberIds, setSelectedMemberIds] = useState([]);
  const [memberSearch, setMemberSearch] = useState('');
  const [quickEvent, setQuickEvent] = useState({
    event_type: 'regular_contact',
    event_date: new Date().toISOString().split('T')[0],
    title: '',
    description: '',
    aid_type: 'education',
    aid_amount: '',
    grief_relationship: '',
    hospital_name: '',
    schedule_frequency: 'one_time',
    payment_date: new Date().toISOString().split('T')[0]
  });
  const [engagementSettings, setEngagementSettings] = useState({
    atRiskDays: 60,
    inactiveDays: 90
  });
  
  useEffect(() => {
    // Load engagement settings from localStorage (set in Settings page)
    const savedSettings = localStorage.getItem('engagement_settings');
    if (savedSettings) {
      setEngagementSettings(JSON.parse(savedSettings));
    }
  }, []);
  
  const handleQuickEvent = async (e) => {
    e.preventDefault();
    if (selectedMemberIds.length === 0) {
      toast.error(t('select_at_least_one_member'));
      return;
    }
    
    // Auto-generate title based on event type (except financial aid)
    const eventTypeNames = {
      birthday: 'Birthday Celebration',
      childbirth: 'New Baby Celebration',
      grief_loss: 'Grief Support',
      new_house: 'New Home Visit',
      accident_illness: 'Medical Support',
      regular_contact: 'Regular Contact',
      financial_aid: quickEvent.title // Use custom title for financial aid
    };
    
    const autoTitle = eventTypeNames[quickEvent.event_type] || quickEvent.title;
    
    try {
      let success = 0;
      for (const memberId of selectedMemberIds) {
        const member = allMembers.find(m => m.id === memberId);
        
        if (quickEvent.event_type === 'financial_aid') {
          if (quickEvent.schedule_frequency === 'one_time') {
            // One-time aid: Create care event
            await axios.post(`${API}/care-events`, {
              member_id: memberId,
              campus_id: member.campus_id,
              event_type: 'financial_aid',
              event_date: quickEvent.payment_date || quickEvent.event_date,
              title: autoTitle,
              description: quickEvent.description,
              aid_type: quickEvent.aid_type,
              aid_amount: parseFloat(quickEvent.aid_amount)
            });
          } else {
            // Scheduled aid: Create schedule
            // Convert Month/Year Selects to date format for monthly
            let startDate = quickEvent.schedule_start_date;
            let endDate = quickEvent.schedule_end_date;
            
            if (quickEvent.schedule_frequency === 'monthly') {
              // Convert start_month + start_year to YYYY-MM-01 format
              const startMonth = quickEvent.start_month || new Date().getMonth() + 1;
              const startYear = quickEvent.start_year || new Date().getFullYear();
              startDate = `${startYear}-${String(startMonth).padStart(2, '0')}-01`;
              
              // Convert end_month + end_year to YYYY-MM-01 format (if provided)
              if (quickEvent.end_month && quickEvent.end_year) {
                endDate = `${quickEvent.end_year}-${String(quickEvent.end_month).padStart(2, '0')}-01`;
              } else {
                endDate = null;
              }
            } else if (quickEvent.schedule_frequency === 'weekly') {
              startDate = new Date().toISOString().split('T')[0]; // Use today for weekly
            }
            
            await axios.post(`${API}/financial-aid-schedules`, {
              member_id: memberId,
              campus_id: member.campus_id,
              title: autoTitle,
              aid_type: quickEvent.aid_type,
              aid_amount: parseFloat(quickEvent.aid_amount),
              frequency: quickEvent.schedule_frequency,
              start_date: startDate,
              end_date: endDate,
              day_of_week: quickEvent.day_of_week,
              day_of_month: quickEvent.day_of_month,
              month_of_year: quickEvent.month_of_year,
              notes: quickEvent.description
            });
          }
        } else {
          // Other events: Create normal care event with auto title
          await axios.post(`${API}/care-events`, {
            member_id: memberId,
            campus_id: member.campus_id,
            event_type: quickEvent.event_type,
            event_date: quickEvent.event_date,
            title: autoTitle,
            description: quickEvent.description,
            grief_relationship: quickEvent.grief_relationship,
            hospital_name: quickEvent.hospital_name
          });
        }
        success++;
      }
      
      toast.success(`Added ${quickEvent.event_type.replace('_', ' ')} for ${success} members!`);
      setQuickEventOpen(false);
      setSelectedMemberIds([]);
      setMemberSearch('');
      setQuickEvent({
        event_type: 'regular_contact',
        event_date: new Date().toISOString().split('T')[0],
        title: '',
        description: '',
        aid_type: 'education',
        aid_amount: '',
        grief_relationship: '',
        hospital_name: '',
        schedule_frequency: 'one_time',
        payment_date: new Date().toISOString().split('T')[0]
      });
      // Refresh dashboard to show new tasks - Invalidate React Query cache
      queryClient.invalidateQueries(['dashboard']);
      queryClient.invalidateQueries(['members']);
    } catch (error) {
      toast.error('Failed to add events');
    }
  };
  
  const toggleMemberSelection = (memberId) => {
    setSelectedMemberIds(prev => 
      prev.includes(memberId) ? prev.filter(id => id !== memberId) : [...prev, memberId]
    );
    setMemberSearch('');
  };
  
  const filteredMembers = allMembers.filter(m => 
    m.name.toLowerCase().includes(memberSearch.toLowerCase())
  );

  
  if (isLoading) return <div>{t('loading')}</div>;
  
  const totalTasks = birthdaysToday.length + griefDue.length + hospitalFollowUp.length + Math.min(atRiskMembers.length, 10);
  
  return (
    <div className="space-y-8 pb-12 max-w-full">
      {/* Welcome Section */}
      <div>
        <h1 className="text-5xl font-playfair font-bold text-foreground mb-2">
          {t('welcome_back')}, {user?.name}!
        </h1>
        <p className="text-muted-foreground text-lg">{t('pastoral_overview')}</p>
      </div>
      
      {/* Stats Cards with Colored Left Borders */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 max-w-full">
        <Card className="card-border-left-teal shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">{t('total_members')}</p>
                <p className="text-2xl sm:text-4xl font-playfair font-bold">805</p>
              </div>
              <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
                <Users className="w-5 h-5 sm:w-7 sm:h-7 text-teal-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-amber shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Tasks Due Today</p>
                <p className="text-2xl sm:text-4xl font-playfair font-bold">
                  {birthdaysToday.filter(b => !b.completed).length + todayTasks.filter(t => !t.completed).length}
                </p>
              </div>
              <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                <Bell className="w-5 h-5 sm:w-7 sm:h-7 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-pink shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Overdue Follow-ups</p>
                <p className="text-2xl sm:text-4xl font-playfair font-bold">{griefDue.length + accidentFollowUp.length + financialAidDue.length}</p>
              </div>
              <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-pink-100 flex items-center justify-center flex-shrink-0">
                <Heart className="w-5 h-5 sm:w-7 sm:h-7 text-pink-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-purple shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Members Needing Care</p>
                <p className="text-2xl sm:text-4xl font-playfair font-bold">{atRiskMembers.length + disconnectedMembers.length}</p>
              </div>
              <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 sm:w-7 sm:h-7 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Quick Actions */}
      <div className="max-w-full">
        <h2 className="text-2xl font-playfair font-bold mb-4">{t('quick_actions')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-full">
          <Dialog open={quickEventOpen} onOpenChange={setQuickEventOpen}>
            <DialogTrigger asChild>
              <Button className="w-full h-14 bg-teal-500 hover:bg-teal-600 text-white text-base font-semibold min-w-0">
                <Plus className="w-5 h-5 mr-2 flex-shrink-0" /><span className="truncate">{t('add_new_care_event')}</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="text-2xl font-playfair">{t('quick_care_event_multi')}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleQuickEvent} className="space-y-4">
                {/* Member Selection */}
                <div className="space-y-2">
                  <Label className="font-semibold">{t('select_members_required')}</Label>
                  <Input
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder={t('form_placeholders.search_name_phone')}
                    className="h-12"
                    autoFocus
                  />
                  
                  {selectedMemberIds.length > 0 && (
                    <div className="p-3 bg-teal-50 rounded border">
                      <p className="font-semibold text-sm mb-2">{t('labels.selected_members_count', {count: selectedMemberIds.length})}:</p>
                      <div className="flex flex-wrap gap-2">
                        {selectedMemberIds.map(id => {
                          const member = allMembers.find(m => m.id === id);
                          return member ? (
                            <span key={id} className="bg-teal-100 text-teal-800 px-2 py-1 rounded text-xs flex items-center gap-1">
                              {member.name}
                              <button type="button" onClick={() => toggleMemberSelection(id)} className="ml-1 text-teal-600">×</button>
                            </span>
                          ) : null;
                        })}
                      </div>
                    </div>
                  )}
                  
                  {memberSearch && (
                    <div className="max-h-48 overflow-y-auto border rounded p-2 space-y-1">
                      {filteredMembers.slice(0, 15).map(member => (
                        <div key={member.id} className="flex items-center gap-2 p-1 hover:bg-muted rounded">
                          <Checkbox
                            checked={selectedMemberIds.includes(member.id)}
                            onCheckedChange={() => toggleMemberSelection(member.id)}
                          />
                          <span className="text-sm">{member.name}</span>
                          <span className="text-xs text-muted-foreground">({member.phone})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* Event Details */}
                <div>
                  <Label className="font-semibold">{t('event_type_required')}</Label>
                  <Select value={quickEvent.event_type} onValueChange={(v) => setQuickEvent({...quickEvent, event_type: v})}>
                    <SelectTrigger className="h-12"><SelectValue placeholder={t('form_placeholders.select_event_type')} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="childbirth">👶 Childbirth</SelectItem>
                      <SelectItem value="grief_loss">💔 Grief/Loss</SelectItem>
                      <SelectItem value="new_house">🏠 New House</SelectItem>
                      <SelectItem value="accident_illness">🚑 Accident/Illness</SelectItem>
                      <SelectItem value="financial_aid">💰 Financial Aid</SelectItem>
                      <SelectItem value="regular_contact">📞 Regular Contact</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Event Date - Calendar Picker with proper z-index */}
                {quickEvent.event_type !== 'financial_aid' && (
                  <div>
                    <Label className="font-semibold">{t('event_date_required')}</Label>
                    <Popover modal={true} open={eventDateOpen} onOpenChange={setEventDateOpen}>
                      <PopoverTrigger asChild>
                        <Button variant="outline" className="w-full h-12 justify-start text-left font-normal" type="button">
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {quickEvent.event_date ? formatDateFns(new Date(quickEvent.event_date), 'dd MMM yyyy') : <span className="text-muted-foreground">Select date...</span>}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="p-0 z-[9999]" side="bottom" align="start">
                        <div className="w-[280px]">
                          <CalendarComponent
                            mode="single"
                            selected={quickEvent.event_date ? new Date(quickEvent.event_date) : undefined}
                            onSelect={(date) => {
                              if (date) {
                                setQuickEvent({...quickEvent, event_date: formatDateFns(date, 'yyyy-MM-dd')});
                                setEventDateOpen(false); // Close calendar after selection
                              }
                            }}
                            initialFocus
                          />
                        </div>
                      </PopoverContent>
                    </Popover>
                  </div>
                )}
                
                <div>
                  <Label className="font-semibold">Description</Label>
                  <Input value={quickEvent.description} onChange={(e) => setQuickEvent({...quickEvent, description: e.target.value})} placeholder={t('form_placeholders.additional_details')} className="h-12" />
                </div>
                
                {/* Title only for Financial Aid */}
                {quickEvent.event_type === 'financial_aid' && (
                  <div>
                        <Label className="font-semibold">Aid Name/Title</Label>
                        <Input value={quickEvent.title} onChange={(e) => setQuickEvent({...quickEvent, title: e.target.value})} placeholder={t('form_placeholders.monthly_education_support')} className="h-12" required />
                  </div>
                )}
                
                {/* Conditional Fields */}
                {quickEvent.event_type === 'grief_loss' && (
                  <div className="space-y-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
                    <p className="text-sm font-medium text-purple-900">⭐ Auto-generates 6-stage grief timeline</p>
                    <div>
                      <Label className="font-semibold">Relationship to Deceased</Label>
                      <Select value={quickEvent.grief_relationship} onValueChange={(v) => setQuickEvent({...quickEvent, grief_relationship: v})} required>
                        <SelectTrigger className="h-12"><SelectValue placeholder={t('form_placeholders.select_relationship')} /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="spouse">Spouse</SelectItem>
                          <SelectItem value="parent">Parent</SelectItem>
                          <SelectItem value="child">Child</SelectItem>
                          <SelectItem value="sibling">Sibling</SelectItem>
                          <SelectItem value="friend">Friend</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
                
                {quickEvent.event_type === 'accident_illness' && (
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <div>
                      <Label className="font-semibold">Hospital/Medical Facility Name</Label>
                      <Input
                        value={quickEvent.hospital_name}
                        onChange={(e) => setQuickEvent({...quickEvent, hospital_name: e.target.value})}
                        placeholder={t('form_placeholders.hospital_example')}
                        className="h-12"
                      />
                    </div>
                  </div>
                )}
                
                {quickEvent.event_type === 'financial_aid' && (
                  <div className="space-y-4 p-4 bg-green-50 rounded-lg border border-green-200">
                    <h4 className="font-semibold text-green-900">Financial Aid Details</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <Label className="font-semibold">Aid Type</Label>
                        <Select value={quickEvent.aid_type} onValueChange={(v) => setQuickEvent({...quickEvent, aid_type: v})} required>
                          <SelectTrigger className="h-12"><SelectValue placeholder={t('form_placeholders.select_aid_type')} /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="education">Education Support</SelectItem>
                            <SelectItem value="medical">Medical Bills</SelectItem>
                            <SelectItem value="emergency">Emergency Relief</SelectItem>
                            <SelectItem value="housing">Housing Assistance</SelectItem>
                            <SelectItem value="food">Food Support</SelectItem>
                            <SelectItem value="funeral_costs">Funeral Costs</SelectItem>
                            <SelectItem value="other">Other</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="font-semibold">Amount (Rp)</Label>
                        <Input
                          type="number"
                          value={quickEvent.aid_amount}
                          onChange={(e) => setQuickEvent({...quickEvent, aid_amount: e.target.value})}
                          placeholder={t('form_placeholders.amount_example')}
                          className="h-12"
                          required
                        />
                      </div>
                    </div>
                    
                    {/* Financial Aid Scheduling */}
                    <div className="space-y-4 border-t pt-4">
                      <h5 className="font-semibold text-green-800">📅 Payment Type</h5>
                      <div>
                        <Label className="font-semibold">Frequency</Label>
                        <Select value={quickEvent.schedule_frequency || 'one_time'} onValueChange={(v) => setQuickEvent({...quickEvent, schedule_frequency: v})}>
                          <SelectTrigger className="h-12"><SelectValue placeholder={t('form_placeholders.select_frequency')} /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="one_time">One-time Payment (already given)</SelectItem>
                            <SelectItem value="weekly">Weekly Schedule (future payments)</SelectItem>
                            <SelectItem value="monthly">Monthly Schedule (future payments)</SelectItem>
                            <SelectItem value="annually">Annual Schedule (future payments)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      {quickEvent.schedule_frequency === 'one_time' && (
                        <div>
                          <Label className="font-semibold">Payment Date</Label>
                          <Popover modal={true} open={paymentDateOpen} onOpenChange={setPaymentDateOpen}>
                            <PopoverTrigger asChild>
                              <Button variant="outline" className="w-full h-12 justify-start text-left font-normal" type="button">
                                <CalendarIcon className="mr-2 h-4 w-4" />
                                {quickEvent.payment_date ? formatDateFns(new Date(quickEvent.payment_date), 'dd MMM yyyy') : <span className="text-muted-foreground">Select payment date...</span>}
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="p-0 z-[9999]" side="bottom" align="start">
                              <div className="w-[280px]">
                                <CalendarComponent
                                  mode="single"
                                  selected={quickEvent.payment_date ? new Date(quickEvent.payment_date) : undefined}
                                  onSelect={(date) => {
                                    if (date) {
                                      setQuickEvent({...quickEvent, payment_date: formatDateFns(date, 'yyyy-MM-dd')});
                                      setPaymentDateOpen(false); // Close calendar
                                    }
                                  }}
                                  initialFocus
                                />
                              </div>
                            </PopoverContent>
                          </Popover>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'weekly' && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-blue-50 rounded">
                          <div>
                            <Label className="font-semibold text-xs">Day of Week *</Label>
                            <Select value={quickEvent.day_of_week || 'monday'} onValueChange={(v) => setQuickEvent({...quickEvent, day_of_week: v})}>
                              <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="monday">{t('days_of_week.monday')}</SelectItem>
                                <SelectItem value="tuesday">{t('days_of_week.tuesday')}</SelectItem>
                                <SelectItem value="wednesday">{t('days_of_week.wednesday')}</SelectItem>
                                <SelectItem value="thursday">{t('days_of_week.thursday')}</SelectItem>
                                <SelectItem value="friday">{t('days_of_week.friday')}</SelectItem>
                                <SelectItem value="saturday">{t('days_of_week.saturday')}</SelectItem>
                                <SelectItem value="sunday">{t('days_of_week.sunday')}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="font-semibold text-xs">End Date (optional)</Label>
                            <Popover modal={true} open={endDateOpen} onOpenChange={setEndDateOpen}>
                              <PopoverTrigger asChild>
                                <Button variant="outline" className="w-full h-12 justify-start text-left font-normal" type="button">
                                  <CalendarIcon className="mr-2 h-4 w-4" />
                                  {quickEvent.schedule_end_date ? formatDateFns(new Date(quickEvent.schedule_end_date), 'dd MMM yyyy') : <span className="text-muted-foreground">{t('form_placeholders.no_end_date')}</span>}
                                </Button>
                              </PopoverTrigger>
                              <PopoverContent className="p-0 z-[9999]" side="bottom" align="start">
                                <div className="w-[280px]">
                                  <CalendarComponent
                                    mode="single"
                                    selected={quickEvent.schedule_end_date ? new Date(quickEvent.schedule_end_date) : undefined}
                                    onSelect={(date) => {
                                      if (date) {
                                        setQuickEvent({...quickEvent, schedule_end_date: formatDateFns(date, 'yyyy-MM-dd')});
                                        setEndDateOpen(false); // Close calendar
                                      }
                                    }}
                                    initialFocus
                                  />
                                </div>
                              </PopoverContent>
                            </Popover>
                          </div>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'monthly' && (
                        <div className="space-y-3 p-3 bg-purple-50 rounded">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <Label className="font-semibold text-xs">Start Month *</Label>
                              <Select value={(quickEvent.start_month || new Date().getMonth() + 1).toString()} onValueChange={(v) => setQuickEvent({...quickEvent, start_month: parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="1">{t('months.january')}</SelectItem>
                                  <SelectItem value="2">{t('months.february')}</SelectItem>
                                  <SelectItem value="3">{t('months.march')}</SelectItem>
                                  <SelectItem value="4">{t('months.april')}</SelectItem>
                                  <SelectItem value="5">{t('months.may')}</SelectItem>
                                  <SelectItem value="6">{t('months.june')}</SelectItem>
                                  <SelectItem value="7">{t('months.july')}</SelectItem>
                                  <SelectItem value="8">{t('months.august')}</SelectItem>
                                  <SelectItem value="9">{t('months.september')}</SelectItem>
                                  <SelectItem value="10">{t('months.october')}</SelectItem>
                                  <SelectItem value="11">{t('months.november')}</SelectItem>
                                  <SelectItem value="12">{t('months.december')}</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="font-semibold text-xs">Start Year *</Label>
                              <Select value={(quickEvent.start_year || new Date().getFullYear()).toString()} onValueChange={(v) => setQuickEvent({...quickEvent, start_year: parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  {[...Array(10)].map((_, i) => {
                                    const year = new Date().getFullYear() + i;
                                    return <SelectItem key={year} value={year.toString()}>{year}</SelectItem>;
                                  })}
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <div>
                            <Label className="font-semibold text-xs">Day of Month *</Label>
                            <Input type="number" min="1" max="31" value={quickEvent.day_of_month || ''} onChange={(e) => setQuickEvent({...quickEvent, day_of_month: parseInt(e.target.value) || 1})} placeholder={t('form_placeholders.day_example')} className="h-12" required />
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <Label className="font-semibold text-xs">End Month (optional)</Label>
                              <Select value={(quickEvent.end_month || 'none').toString()} onValueChange={(v) => setQuickEvent({...quickEvent, end_month: v === 'none' ? null : parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue placeholder={t('form_placeholders.no_end_date')} /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">{t('form_placeholders.no_end_date')}</SelectItem>
                                  <SelectItem value="1">{t('months.january')}</SelectItem>
                                  <SelectItem value="2">{t('months.february')}</SelectItem>
                                  <SelectItem value="3">{t('months.march')}</SelectItem>
                                  <SelectItem value="4">{t('months.april')}</SelectItem>
                                  <SelectItem value="5">{t('months.may')}</SelectItem>
                                  <SelectItem value="6">{t('months.june')}</SelectItem>
                                  <SelectItem value="7">{t('months.july')}</SelectItem>
                                  <SelectItem value="8">{t('months.august')}</SelectItem>
                                  <SelectItem value="9">{t('months.september')}</SelectItem>
                                  <SelectItem value="10">{t('months.october')}</SelectItem>
                                  <SelectItem value="11">{t('months.november')}</SelectItem>
                                  <SelectItem value="12">{t('months.december')}</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="font-semibold text-xs">End Year (optional)</Label>
                              <Select value={(quickEvent.end_year || 'none').toString()} onValueChange={(v) => setQuickEvent({...quickEvent, end_year: v === 'none' ? null : parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue placeholder={t('form_placeholders.no_end_date')} /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">{t('form_placeholders.no_end_date')}</SelectItem>
                                  {[...Array(10)].map((_, i) => {
                                    const year = new Date().getFullYear() + i;
                                    return <SelectItem key={year} value={year.toString()}>{year}</SelectItem>;
                                  })}
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'annually' && (
                        <div className="grid grid-cols-2 gap-3 p-3 bg-orange-50 rounded">
                          <div>
                            <Label className="text-xs">Month of Year</Label>
                            <Select value={(quickEvent.month_of_year || 1).toString()} onValueChange={(v) => setQuickEvent({...quickEvent, month_of_year: parseInt(v)})}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="1">January</SelectItem>
                                <SelectItem value="2">February</SelectItem>
                                <SelectItem value="3">March</SelectItem>
                                <SelectItem value="4">April</SelectItem>
                                <SelectItem value="5">May</SelectItem>
                                <SelectItem value="6">June</SelectItem>
                                <SelectItem value="7">July</SelectItem>
                                <SelectItem value="8">August</SelectItem>
                                <SelectItem value="9">September</SelectItem>
                                <SelectItem value="10">October</SelectItem>
                                <SelectItem value="11">November</SelectItem>
                                <SelectItem value="12">December</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs">End Year</Label>
                            <Input type="number" min={new Date().getFullYear()} value={quickEvent.schedule_end_date ? new Date(quickEvent.schedule_end_date).getFullYear() : ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value ? `${e.target.value}-12-31` : ''})} placeholder="2030" />
                          </div>
                        </div>
                      )}
                    </div>
                    
                    <p className="text-sm text-green-700">
                      Total: Rp {((quickEvent.aid_amount || 0) * selectedMemberIds.length).toLocaleString('id-ID')} for {selectedMemberIds.length} members
                    </p>
                  </div>
                )}
                
                {/* Action Buttons */}
                <div className="flex gap-3 pt-4">
                  <Button type="button" variant="outline" onClick={() => setQuickEventOpen(false)} className="flex-1 h-12">
                    {t('buttons.cancel')}
                  </Button>
                  <Button type="submit" className="flex-1 h-12 bg-teal-500 hover:bg-teal-600 text-white font-semibold" disabled={selectedMemberIds.length === 0}>
                    {t('buttons.save_care_event')}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
          <Link to="/members">
            <Button className="w-full h-14 bg-amber-500 hover:bg-amber-600 text-white text-base font-semibold">
              <Users className="w-5 h-5 mr-2" />{t('view_all_members')}
            </Button>
          </Link>
        </div>
      </div>
      
      {/* Task Management */}
      <div>
        <h2 className="text-2xl font-playfair font-bold mb-4">{t('todays_tasks_reminders')}</h2>
        <p className="text-muted-foreground mb-4">
          {birthdaysToday.filter(b => !b.completed).length + todayTasks.filter(t => !t.completed).length} {t('tasks_need_attention')}
        </p>
      </div>
      
      <Tabs defaultValue="today" className="w-full">
        <div className="overflow-hidden">
          <TabsList className="flex w-full">
            <TabsTrigger value="today" className="flex-1">
              <Bell className="w-4 h-4 mr-2" />
              <span>{t('main_tabs.today')}</span>
              <span className="ml-1 text-xs">({birthdaysToday.filter(b => !b.completed).length + todayTasks.filter(t => !t.completed).length})</span>
            </TabsTrigger>
            <TabsTrigger value="overdue" className="flex-1">
              <AlertTriangle className="w-4 h-4 mr-2" />
              <span>{t('main_tabs.overdue')}</span>
              <span className="ml-1 text-xs">({overdueBirthdays.length + griefDue.length + accidentFollowUp.length + financialAidDue.length + atRiskMembers.length + disconnectedMembers.length})</span>
            </TabsTrigger>
            <TabsTrigger value="upcoming" className="flex-1">
              <Heart className="w-4 h-4 mr-2" />
              <span>{t('main_tabs.upcoming')}</span>
              <span className="ml-1 text-xs">({upcomingTasks.length})</span>
            </TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="today" className="space-y-4">
          {birthdaysToday.length === 0 && todayTasks.length === 0 ? (
              <CardContent className="p-6 text-center">{t('no_urgent_tasks_today')}</CardContent>
          ) : (
            <>
              {/* Birthdays Today */}
              {birthdaysToday.length > 0 && (
                <Card className="card-border-left-amber">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-xl">
                      🎂 {t('birthdays_today')} ({birthdaysToday.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {birthdaysToday.map(event => (
                        <div key={event.id} className="p-4 bg-amber-50 rounded-lg border border-amber-200 relative hover:shadow-lg transition-all">
                          {/* Overdue Badge - Top Right */}
                          {event.days_overdue > 0 && (
                            <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                              {event.days_overdue}d overdue
                            </span>
                          )}
                          
                          <div className="flex items-start gap-3 mb-3">
                            {/* Avatar with colored ring - Simplified */}
                            <div className="flex-shrink-0 rounded-full ring-2 ring-amber-400">
                              <MemberAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} size="md" />
                            </div>
                            
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${event.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                {event.member_name}
                              </Link>
                              {event.member_phone && (
                                <a href={`tel:${event.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {event.member_phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                {event.completed ? "✅ Birthday contact completed" : t('labels.call_wish_birthday')}
                                {event.member_age && <span className="ml-2 text-xs">• {event.member_age} years old</span>}
                              </p>
                            </div>
                          </div>
                          
                          {/* Actions - Horizontal compact layout */}
                          <div className="flex gap-2">
                            <Button 
                              size="default" 
                              className="bg-amber-500 hover:bg-amber-600 text-white h-11 flex-1 min-w-0" 
                              asChild
                            >
                              <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            {event.completed ? (
                              <Button size="default" variant="outline" disabled className="bg-white text-green-700 border-green-300 h-11 flex-1 min-w-0">
                                <Check className="w-4 h-4 mr-1" />
                                <span className="truncate">{t('completed')}</span>
                              </Button>
                            ) : (
                              <Button size="default" variant="outline" onClick={() => { triggerHaptic(); markBirthdayComplete(event.id, queryClient, t); }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                                <Check className="w-4 h-4 mr-1" />
                                <span className="truncate">{t('mark_complete')}</span>
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* All Other Tasks Due Today */}
              {todayTasks.length > 0 && (
                <Card className="card-border-left-teal">
                  <CardHeader>
                    <CardTitle className="text-xl">{t('other_tasks_due_today')} ({todayTasks.length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {todayTasks.map((task, index) => {
                        const typeConfig = {
                          grief_support: { icon: '💔', color: 'pink', bgClass: 'bg-pink-50', borderClass: 'border-pink-200', btnClass: 'bg-pink-500 hover:bg-pink-600', label: t('grief_support') },
                          accident_followup: { icon: '🏥', color: 'blue', bgClass: 'bg-blue-50', borderClass: 'border-blue-200', btnClass: 'bg-blue-500 hover:bg-blue-600', label: t('accident_followup_label') },
                          financial_aid: { icon: '💰', color: 'green', bgClass: 'bg-purple-50', borderClass: 'border-purple-200', btnClass: 'bg-purple-500 hover:bg-purple-600', label: t('financial_aid') }
                        };
                        const config = typeConfig[task.type] || { icon: '📋', color: 'gray', bgClass: 'bg-gray-50', borderClass: 'border-gray-200', btnClass: 'bg-gray-500 hover:bg-gray-600', label: 'Task' };
                        
                        return (
                          <div key={index} className={`p-4 ${config.bgClass} rounded-lg border ${config.borderClass} relative hover:shadow-lg transition-all`}>
                            {/* Overdue Badge - Top Right */}
                            {task.days_overdue > 0 && (
                              <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                                {task.days_overdue}d overdue
                              </span>
                            )}
                            
                            <div className="flex items-start gap-3 mb-3">
                              {/* Avatar with colored ring - Simplified */}
                              <div className={`flex-shrink-0 rounded-full ring-2 ${
                                config.color === 'pink' ? 'ring-pink-400' : 
                                config.color === 'blue' ? 'ring-blue-400' : 
                                'ring-purple-400'
                              }`}>
                                <MemberAvatar member={{name: task.member_name, photo_url: task.member_photo_url}} size="md" />
                              </div>
                              
                              <div className="flex-1 min-w-0">
                                <Link to={`/members/${task.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                  {task.member_name}
                                </Link>
                                {task.member_phone && (
                                  <a href={`tel:${task.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                    📞 {task.member_phone}
                                  </a>
                                )}
                                <p className="text-sm text-muted-foreground mt-1">
                                  <span className="font-medium">{config.label}</span>
                                  {task.type === 'grief_support' && (
                                    <span className="ml-2 px-2 py-0.5 bg-purple-500 text-white text-xs rounded">
                                      {getGriefStageBadge(task.data.stage)}
                                    </span>
                                  )}
                                  {task.type !== 'grief_support' && `: ${task.details}`}
                                  {task.days_since_last_contact > 0 && <span className="ml-2 text-xs">• Last contact {task.days_since_last_contact}d ago</span>}
                                </p>
                              </div>
                            </div>
                            
                            {/* Actions - Horizontal compact layout */}
                            <div className="flex gap-2">
                              <Button size="default" className={`${config.btnClass} text-white h-11 flex-1 min-w-0`} asChild>
                                <a href={formatPhoneForWhatsApp(task.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                  <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                  </svg>
                                  <span className="truncate">{t('contact_whatsapp')}</span>
                                </a>
                              </Button>
                              
                              {task.type === 'financial_aid' ? (
                                // Financial aid: Compact horizontal buttons
                                <>
                                  <Button size="default" variant="outline" onClick={async () => {
                                    try {
                                      await axios.post(`${API}/financial-aid-schedules/${task.data.id}/mark-distributed`);
                                      toast.success(t('toasts.payment_distributed'));
                                      await queryClient.invalidateQueries(['dashboard']);
                                    } catch (error) {
                                      toast.error(t('toasts.failed_mark_distributed'));
                                    }
                                  }} className="h-11 flex-1 min-w-0">
                                    <Check className="w-4 h-4 mr-1" />
                                    <span className="truncate">{t('mark_distributed')}</span>
                                  </Button>
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                        <MoreVertical className="w-5 h-5" />
                                      </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-40">
                                      <DropdownMenuItem onClick={async () => {
                                        try {
                                          await axios.post(`${API}/financial-aid-schedules/${task.data.id}/ignore`);
                                          toast.success(t('toasts.financial_aid_ignored'));
                                          await queryClient.invalidateQueries(['dashboard']);
                                        } catch (error) {
                                          toast.error(t('toasts.failed_ignore'));
                                        }
                                      }}>
                                        {t('ignore')}
                                      </DropdownMenuItem>
                                      <DropdownMenuItem 
                                        className="text-red-600"
                                        onClick={async () => {
                                          try {
                                            await axios.post(`${API}/financial-aid-schedules/${task.data.id}/stop`);
                                            toast.success(t('toasts.schedule_stopped'));
                                            await queryClient.invalidateQueries(['dashboard']);
                                          } catch (error) {
                                            toast.error(t('toasts.failed_stop'));
                                          }
                                        }}
                                      >
                                        {t('stop_schedule')}
                                      </DropdownMenuItem>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </>
                              ) : (
                                // Grief/Accident: Compact horizontal buttons
                                <>
                                  <Button size="default" variant="outline" onClick={async () => {
                                    triggerHaptic();
                                    try {
                                      if (task.type === 'grief_support') {
                                        await markGriefStageComplete(task.data.id, queryClient, t);
                                      } else if (task.type === 'accident_followup') {
                                        await axios.post(`${API}/accident-followup/${task.data.id}/complete`);
                                        toast.success(t('toasts.followup_completed'));
                                        await queryClient.invalidateQueries(['dashboard']);
                                      }
                                    } catch (error) {
                                      toast.error(t('toasts.failed_mark_completed'));
                                    }
                                  }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                                    <Check className="w-4 h-4 mr-1" />
                                    <span className="truncate">{t('mark_complete')}</span>
                                  </Button>
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                        <MoreVertical className="w-5 h-5" />
                                      </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-32">
                                      <DropdownMenuItem onClick={async () => {
                                        try {
                                          if (task.type === 'grief_support') {
                                            await axios.post(`${API}/grief-support/${task.data.id}/ignore`);
                                            toast.success(t('toasts.grief_ignored'));
                                          } else if (task.type === 'accident_followup') {
                                            await axios.post(`${API}/accident-followup/${task.data.id}/ignore`);
                                            toast.success(t('toasts.accident_ignored'));
                                          }
                                          await queryClient.invalidateQueries(['dashboard']);
                                        } catch (error) {
                                      toast.error('Failed to ignore');
                                    }
                                  }}>
                                    {t('ignore')}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                              </>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>
        
        {/* Overdue Tab with Nested Tabs */}
        <TabsContent value="overdue" className="space-y-4">
          <Tabs defaultValue="birthdays" className="w-full" onValueChange={(v) => setActiveOverdueTab(v)}>
            <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
              <TabsList className="inline-flex min-w-full w-max sm:w-full">
                <TabsTrigger value="birthdays" className="flex-shrink-0">
                  <Cake className="w-4 h-4" />
                  {activeOverdueTab === 'birthdays' ? (
                    <span className="ml-2">{t('nested_tabs.birthday')} ({overdueBirthdays.length})</span>
                  ) : (
                    <span className="ml-1">({overdueBirthdays.length})</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="followups" className="flex-shrink-0">
                  <Hospital className="w-4 h-4" />
                  {activeOverdueTab === 'followups' ? (
                    <span className="ml-2">{t('nested_tabs.followups')} ({griefDue.length + accidentFollowUp.length})</span>
                  ) : (
                    <span className="ml-1">({griefDue.length + accidentFollowUp.length})</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="financial" className="flex-shrink-0">
                  <DollarSign className="w-4 h-4" />
                  {activeOverdueTab === 'financial' ? (
                    <span className="ml-2">{t('nested_tabs.aid')} ({financialAidDue.length})</span>
                  ) : (
                    <span className="ml-1">({financialAidDue.length})</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="atrisk" className="flex-shrink-0">
                  <AlertTriangle className="w-4 h-4" />
                  {activeOverdueTab === 'atrisk' ? (
                    <span className="ml-2">{t('nested_tabs.at_risk')} ({atRiskMembers.length})</span>
                  ) : (
                    <span className="ml-1">({atRiskMembers.length})</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="disconnected" className="flex-shrink-0">
                  <Users className="w-4 h-4" />
                  {activeOverdueTab === 'disconnected' ? (
                    <span className="ml-2">{t('nested_tabs.inactive')} ({disconnectedMembers.length})</span>
                  ) : (
                    <span className="ml-1">({disconnectedMembers.length})</span>
                  )}
                </TabsTrigger>
              </TabsList>
            </div>
            
            {/* Birthday Child Tab */}
            <TabsContent value="birthdays" className="space-y-4 mt-4">
              {overdueBirthdays.length === 0 ? (
                <Card>
                  <CardContent className="p-8 text-center text-muted-foreground">
                    {t('no_overdue_birthdays')}
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-amber-200">
                  <CardHeader>
                    <CardTitle>{t('overdue_birthdays')} ({overdueBirthdays.length})</CardTitle>
                    <CardDescription>{t('birthdays_passed_not_acknowledged')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {overdueBirthdays
                        .sort((a, b) => (b.days_overdue || 0) - (a.days_overdue || 0))
                        .map(event => (
                        <div key={event.id} className="p-4 bg-amber-50 rounded-lg border border-amber-200 relative hover:shadow-lg transition-all">
                          {event.days_overdue > 0 && (
                            <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                              {event.days_overdue}d overdue
                            </span>
                          )}
                          <div className="flex items-start gap-3 mb-3">
                            <div className="flex-shrink-0 rounded-full ring-2 ring-amber-400">
                              <MemberAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} size="md" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${event.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                {event.member_name}
                              </Link>
                              {event.member_phone && event.member_phone !== 'null' && event.member_phone !== 'NULL' && (
                                <a href={`tel:${event.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {event.member_phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                {formatDate(event.event_date, 'dd MMM yyyy')}
                                {event.member_age && <span className="ml-2 text-xs">• {event.member_age} years old</span>}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-amber-500 hover:bg-amber-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button size="default" variant="outline" onClick={async () => {
                              triggerHaptic();
                              try {
                                await axios.post(`${API}/care-events/${event.id}/complete`);
                                toast.success(t('toasts.birthday_marked_completed'));
                                await queryClient.invalidateQueries(['dashboard']);
                              } catch (error) {
                                toast.error(t('toasts.failed_mark_completed'));
                              }
                            }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_complete')}</span>
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                  <MoreVertical className="w-5 h-5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-32">
                                <DropdownMenuItem onClick={async () => {
                                  try {
                                    await axios.post(`${API}/care-events/${event.id}/ignore`);
                                    toast.success(t('toasts.birthday_ignored'));
                                    await queryClient.invalidateQueries(['dashboard']);
                                  } catch (error) {
                                    toast.error('Failed to ignore');
                                  }
                                }}>
                                {t('ignore')}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
            
            {/* Followups Child Tab */}
            <TabsContent value="followups" className="space-y-4 mt-4">
              {/* Accident/Illness Follow-ups */}
              {hospitalFollowUp.length > 0 && (
                <Card className="card-border-left-blue">
                  <CardHeader>
                    <CardTitle>Hospital Visit Follow-ups</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {hospitalFollowUp.map(event => (
                        <div key={event.id} className="p-4 bg-blue-50 rounded-lg border border-blue-200 relative hover:shadow-lg transition-all">
                          {/* Overdue Badge */}
                          {event.days_overdue > 0 && (
                            <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                              {event.days_overdue}d overdue
                            </span>
                          )}
                          
                          <div className="flex items-start gap-3 mb-3">
                            {/* Avatar with blue ring */}
                            <div className="flex-shrink-0 rounded-full ring-2 ring-blue-400">
                              <MemberAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} size="md" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${event.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                {event.member_name}
                              </Link>
                              {event.member_phone && event.member_phone !== 'null' && event.member_phone !== 'NULL' && (
                                <a href={`tel:${event.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {event.member_phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                {event.followup_reason}
                                {event.days_since_last_contact && <span className="ml-2 text-xs">• Last contact {event.days_since_last_contact}d ago</span>}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-blue-500 hover:bg-blue-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button size="default" variant="outline" onClick={() => { triggerHaptic(); markAccidentComplete(event.id, queryClient, t); }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_complete')}</span>
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Accident/Illness Recovery Follow-ups */}
              {accidentFollowUp.length > 0 && (
                <Card className="card-border-left-teal">
                  <CardHeader>
                    <CardTitle>{t('accident_illness_recovery_followups')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {accidentFollowUp.map(followup => (
                        <div key={followup.id} className="p-4 bg-teal-50 rounded-lg border border-teal-200 relative hover:shadow-lg transition-all">
                          {/* Overdue Badge - Better aligned */}
                          {followup.days_overdue > 0 && (
                            <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                              {followup.days_overdue}d overdue
                            </span>
                          )}
                          
                          <div className="flex items-start gap-3 mb-3">
                            {/* Avatar with teal ring */}
                            <div className="flex-shrink-0 rounded-full ring-2 ring-teal-400">
                              <MemberAvatar member={{name: followup.member_name, photo_url: followup.member_photo_url}} size="md" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${followup.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                {followup.member_name}
                              </Link>
                              {followup.member_phone && (
                                <a href={`tel:${followup.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {followup.member_phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                <span className="px-2 py-0.5 bg-teal-500 text-white text-xs rounded mr-2">
                                  {getAccidentStageBadge(followup.stage)}
                                </span>
                                Due: {formatDate(followup.scheduled_date)}
                                {followup.days_since_last_contact && <span className="ml-2 text-xs">• Last contact {followup.days_since_last_contact}d ago</span>}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-teal-500 hover:bg-teal-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(followup.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button size="default" variant="outline" onClick={async () => {
                              triggerHaptic();
                              try {
                                await axios.post(`${API}/accident-followup/${followup.id}/complete`);
                                toast.success(t('toasts.accident_completed'));
                                await queryClient.invalidateQueries(['dashboard']);
                              } catch (error) {
                                toast.error(t('toasts.failed_complete'));
                              }
                            }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_complete')}</span>
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                  <MoreVertical className="w-5 h-5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-32">
                                <DropdownMenuItem onClick={async () => {
                                  try {
                                    await axios.post(`${API}/accident-followup/${followup.id}/ignore`);
                                    toast.success(t('toasts.accident_ignored'));
                                    await queryClient.invalidateQueries(['dashboard']);
                                  } catch (error) {
                                    toast.error('Failed to ignore');
                                  }
                                }}>
                                {t('ignore')}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Grief Support Follow-ups */}
              {griefDue.length > 0 && (
                <Card className="card-border-left-purple">
                  <CardHeader>
                    <CardTitle>{t('grief_support_followups')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {griefDue.map(stage => (
                        <div key={stage.id} className="p-4 bg-purple-50 rounded-lg border border-purple-200 relative hover:shadow-lg transition-all">
                          {/* Overdue Badge */}
                          {stage.days_overdue > 0 && (
                            <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                              {stage.days_overdue}d overdue
                            </span>
                          )}
                          
                          <div className="flex items-start gap-3 mb-3">
                            {/* Avatar with purple ring */}
                            <div className="flex-shrink-0 rounded-full ring-2 ring-purple-400">
                              <MemberAvatar member={{name: stage.member_name, photo_url: stage.member_photo_url}} size="md" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${stage.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                {stage.member_name}
                              </Link>
                              {stage.member_phone && (
                                <a href={`tel:${stage.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {stage.member_phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                <span className="px-2 py-0.5 bg-purple-500 text-white text-xs rounded mr-2">
                                  {getGriefStageBadge(stage.stage)}
                                </span>
                                after mourning
                                {stage.days_since_last_contact && <span className="ml-2 text-xs">• Last contact {stage.days_since_last_contact}d ago</span>}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-purple-500 hover:bg-purple-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(stage.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button size="default" variant="outline" onClick={() => { triggerHaptic(); markGriefStageComplete(stage.id, queryClient, t); }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_complete')}</span>
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                  <MoreVertical className="w-5 h-5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-32">
                                <DropdownMenuItem onClick={async () => {
                                  try {
                                    await axios.post(`${API}/grief-support/${stage.id}/ignore`);
                                    toast.success(t('toasts.grief_ignored'));
                                    await queryClient.invalidateQueries(['dashboard']);
                                  } catch (error) {
                                    toast.error('Failed to ignore');
                                  }
                                }}>
                                {t('ignore')}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {hospitalFollowUp.length === 0 && griefDue.length === 0 && accidentFollowUp.length === 0 && (
                <Card><CardContent className="p-6 text-center">No follow-ups needed today</CardContent></Card>
              )}
            </TabsContent>
            
            {/* Financial Child Tab */}
            <TabsContent value="financial" className="space-y-4 mt-4">
              {financialAidDue.length === 0 ? (
                <Card>
                  <CardContent className="p-8 text-center text-muted-foreground">
                    {t('no_overdue_financial_aid')}
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-purple-200">
                  <CardHeader>
                    <CardTitle>{t('financial_aid_overdue')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {financialAidDue.map(schedule => (
                        <div key={schedule.id} className="p-4 bg-purple-50 rounded-lg border border-purple-200 relative hover:shadow-lg transition-all">
                          {/* Overdue Badge */}
                          {schedule.days_overdue > 0 && (
                            <span className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                              {schedule.days_overdue}d overdue
                            </span>
                          )}
                          
                          <div className="flex items-start gap-3 mb-3">
                            <div className="flex-shrink-0 rounded-full ring-2 ring-purple-400">
                              <MemberAvatar 
                                member={{name: schedule.member_name, photo_url: schedule.member_photo_url}} 
                                size="md" 
                              />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${schedule.member_id}`} className="font-semibold text-base hover:text-teal-600">
                                {schedule.member_name}
                              </Link>
                              {schedule.member_phone && (
                                <a href={`tel:${schedule.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {schedule.member_phone}
                                </a>
                              )}
                              <p className="text-lg font-bold text-foreground mt-1">
                                Rp {schedule.aid_amount?.toLocaleString('id-ID')}
                              </p>
                              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2 flex-wrap">
                                <span className="inline-flex items-center gap-1">
                                  🔄 {schedule.frequency.charAt(0).toUpperCase() + schedule.frequency.slice(1)}
                                </span>
                                <span>•</span>
                                <span>{schedule.aid_type.charAt(0).toUpperCase() + schedule.aid_type.slice(1)}</span>
                              </p>
                              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                                <span className="inline-flex items-center gap-1">
                                  📅 {formatDate(schedule.next_occurrence)}
                                </span>
                                {schedule.member_age && (
                                  <>
                                    <span>•</span>
                                    <span>{schedule.member_age} years old</span>
                                  </>
                                )}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-purple-500 hover:bg-purple-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(schedule.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button 
                              size="default" 
                              variant="outline" 
                              onClick={async () => {
                                triggerHaptic();
                                if (window.confirm(t('confirmations.mark_distributed', {name: schedule.member_name}))) {
                                  try {
                                    await axios.post(`${API}/financial-aid-schedules/${schedule.id}/mark-distributed`);
                                    toast.success(t('toasts.payment_distributed_advanced'));
                                    await queryClient.invalidateQueries(['dashboard']);
                                  } catch (error) {
                                    toast.error('Failed to mark as distributed');
                                  }
                                }
                              }}
                              className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50"
                            >
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_distributed')}</span>
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                  <MoreVertical className="w-5 h-5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-40">
                                <DropdownMenuItem onClick={async () => {
                                  try {
                                    await axios.post(`${API}/financial-aid-schedules/${schedule.id}/ignore`);
                                    toast.success(t('toasts.financial_aid_schedule_ignored'));
                                    await queryClient.invalidateQueries(['dashboard']);
                                  } catch (error) {
                                    toast.error('Failed to ignore');
                                  }
                                }}>
                                {t('ignore')}
                                </DropdownMenuItem>
                                <DropdownMenuItem 
                                  className="text-red-600"
                                  onClick={async () => {
                                    if (window.confirm(t('confirmations.stop_schedule', {name: schedule.member_name}))) {
                                      try {
                                        await axios.post(`${API}/financial-aid-schedules/${schedule.id}/stop`);
                                        toast.success(t('toasts.schedule_stopped'));
                                        await queryClient.invalidateQueries(['dashboard']);
                                      } catch (error) {
                                        toast.error(t('toasts.failed_stop_schedule'));
                                      }
                                    }
                                  }}
                                >
                                {t('stop_schedule')}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
            
            {/* At Risk Child Tab */}
            <TabsContent value="atrisk" className="space-y-4 mt-4">
              {atRiskMembers.length === 0 ? (
                <Card>
                  <CardContent className="p-8 text-center text-muted-foreground">
                    No members at risk
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-amber-200">
                  <CardHeader>
                    <CardTitle>{t('members_at_risk_days', {min: engagementSettings.atRiskDays, max: engagementSettings.inactiveDays-1})}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {atRiskMembers.map(member => (
                        <div key={member.id} className="p-4 bg-amber-50 rounded-lg border border-amber-200 hover:shadow-lg transition-all">
                          <div className="flex items-start gap-3 mb-3">
                            <div className="flex-shrink-0 rounded-full ring-2 ring-amber-400">
                              <MemberAvatar member={member} size="md" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${member.id}`} className="font-semibold text-base hover:text-teal-600">
                                {member.name}
                              </Link>
                              {member.phone && member.phone !== 'null' && member.phone !== 'NULL' && (
                                <a href={`tel:${member.phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {member.phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                {member.days_since_last_contact} days since contact
                                {member.age && <span className="ml-2 text-xs">• {member.age} years old</span>}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-amber-500 hover:bg-amber-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button size="default" variant="outline" onClick={() => { triggerHaptic(); markMemberContacted(member.id, member.name, user, queryClient, t); }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('buttons.contacted')}</span>
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
            
            {/* Disconnected Child Tab */}
            <TabsContent value="disconnected" className="space-y-4 mt-4">
              {disconnectedMembers.length === 0 ? (
                <Card>
                  <CardContent className="p-8 text-center text-muted-foreground">
                    No disconnected members
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-red-200">
                  <CardHeader>
                    <CardTitle>{t('members_disconnected_days', {days: engagementSettings.inactiveDays})}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {disconnectedMembers.slice(0, 15).map(member => (
                        <div key={member.id} className="p-4 bg-red-50 rounded-lg border border-red-200 hover:shadow-lg transition-all">
                          <div className="flex items-start gap-3 mb-3">
                            <div className="flex-shrink-0 rounded-full ring-2 ring-red-400">
                              <MemberAvatar member={member} size="md" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Link to={`/members/${member.id}`} className="font-semibold text-base hover:text-teal-600">
                                {member.name}
                              </Link>
                              {member.phone && member.phone !== 'null' && member.phone !== 'NULL' && (
                                <a href={`tel:${member.phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                  📞 {member.phone}
                                </a>
                              )}
                              <p className="text-sm text-muted-foreground mt-1">
                                {member.days_since_last_contact} days since contact
                                {member.age && <span className="ml-2 text-xs">• {member.age} years old</span>}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="default" className="bg-red-500 hover:bg-red-600 text-white h-11 flex-1 min-w-0" asChild>
                              <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            <Button size="default" variant="outline" onClick={() => { triggerHaptic(); markMemberContacted(member.id, member.name, user, queryClient, t); }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('buttons.contacted')}</span>
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </TabsContent>
        
        <TabsContent value="upcoming" className="space-y-4">
          {upcomingTasks.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                {t('no_upcoming_tasks')}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t('upcoming_tasks_next_7_days')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {upcomingTasks.map((task, index) => {
                    const taskDate = new Date(task.date);
                    const todayDate = new Date();
                    taskDate.setHours(0, 0, 0, 0);
                    todayDate.setHours(0, 0, 0, 0);
                    const daysUntil = Math.round((taskDate - todayDate) / (1000 * 60 * 60 * 24));
                    
                    const typeConfig = {
                      birthday: { icon: '🎂', color: 'amber', ringColor: 'ring-amber-400', bgClass: 'bg-amber-50', borderClass: 'border-amber-200', btnClass: 'bg-amber-500 hover:bg-amber-600', label: 'Birthday' },
                      grief_support: { icon: '💔', color: 'pink', ringColor: 'ring-purple-400', bgClass: 'bg-purple-50', borderClass: 'border-purple-200', btnClass: 'bg-purple-500 hover:bg-purple-600', label: 'Grief Support' },
                      accident_followup: { icon: '🏥', color: 'blue', ringColor: 'ring-teal-400', bgClass: 'bg-teal-50', borderClass: 'border-teal-200', btnClass: 'bg-teal-500 hover:bg-teal-600', label: 'Accident Follow-up' },
                      financial_aid: { icon: '💰', color: 'green', ringColor: 'ring-purple-400', bgClass: 'bg-purple-50', borderClass: 'border-purple-200', btnClass: 'bg-purple-500 hover:bg-purple-600', label: 'Financial Aid' }
                    };
                    const config = typeConfig[task.type] || { icon: '📋', color: 'gray', ringColor: 'ring-gray-400', bgClass: 'bg-gray-50', borderClass: 'border-gray-200', btnClass: 'bg-gray-500 hover:bg-gray-600', label: 'Task' };
                    
                    return (
                      <div key={index} className={`p-4 ${config.bgClass} rounded-lg border ${config.borderClass} relative hover:shadow-lg transition-all`}>
                        {/* Days Until Badge - Top Right */}
                        <span className="absolute top-3 right-3 px-2 py-1 bg-blue-500 text-white text-xs font-semibold rounded shadow-sm z-10">
                          in {daysUntil}d
                        </span>
                        
                        <div className="flex items-start gap-3 mb-3">
                          {/* Avatar with colored ring */}
                          <div className={`flex-shrink-0 rounded-full ring-2 ${config.ringColor}`}>
                            <MemberAvatar member={{name: task.member_name, photo_url: task.member_photo_url}} size="md" />
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <Link to={`/members/${task.member_id}`} className="font-semibold text-base hover:text-teal-600">
                              {task.member_name}
                            </Link>
                            {task.member_phone && task.member_phone !== 'null' && task.member_phone !== 'NULL' && (
                              <a href={`tel:${task.member_phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1">
                                📞 {task.member_phone}
                              </a>
                            )}
                            <p className="text-sm text-muted-foreground mt-1">
                              {task.type === 'birthday' ? (
                                <>
                                  <span className="font-medium">Birthday</span>
                                  {task.member_age && typeof task.member_age === 'number' && (
                                    <span className="ml-2 text-xs">• Will be {task.member_age + 1} years old</span>
                                  )}
                                </>
                              ) : task.type === 'accident_followup' ? (
                                <>
                                  <span className="font-medium">{config.label}:</span> {getAccidentStageBadge(task.data.stage)}
                                </>
                              ) : task.type === 'grief_support' ? (
                                <>
                                  <span className="px-2 py-0.5 bg-purple-500 text-white text-xs rounded mr-2">
                                    {getGriefStageBadge(task.data.stage)}
                                  </span>
                                  after mourning
                                </>
                              ) : (
                                <>
                                  <span className="font-medium">{config.label}:</span> {task.details}
                                </>
                              )}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              📅 {formatDate(task.date, 'dd MMM yyyy')}
                            </p>
                          </div>
                        </div>
                        
                        {/* Actions */}
                        <div className="flex gap-2">
                          {task.member_phone && task.member_phone !== 'null' && task.member_phone !== 'NULL' && (
                            <Button size="default" className={`${config.btnClass} text-white h-11 flex-1 min-w-0`} asChild>
                              <a href={formatPhoneForWhatsApp(task.member_phone)} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                                </svg>
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                          )}
                          
                          {/* Complete Button - Type-specific */}
                          {task.type === 'financial_aid' ? (
                            <Button size="default" variant="outline" onClick={async () => {
                              triggerHaptic();
                              try {
                                await axios.post(`${API}/financial-aid-schedules/${task.data.id}/mark-distributed`);
                                toast.success(t('toasts.payment_distributed'));
                                await queryClient.invalidateQueries(['dashboard']);
                              } catch (error) {
                                toast.error(t('toasts.failed'));
                              }
                            }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_distributed')}</span>
                            </Button>
                          ) : (
                            <Button size="default" variant="outline" onClick={async () => {
                              triggerHaptic();
                              try {
                                let endpoint;
                                if (task.type === 'grief_support') endpoint = `${API}/grief-support/${task.data.id}/complete`;
                                else if (task.type === 'accident_followup') endpoint = `${API}/accident-followup/${task.data.id}/complete`;
                                else if (task.type === 'birthday') endpoint = `${API}/care-events/${task.data.id}/complete`;
                                
                                // Debug: console.log('Upcoming complete:', task.type, endpoint, task.data);
                                
                                if (endpoint) {
                                  await axios.post(endpoint);
                                  toast.success(t('toasts.completed'));
                                  await queryClient.invalidateQueries(['dashboard']);
                                }
                              } catch (error) {
                                console.error('Error completing upcoming task:', error);
                                toast.error(t('toasts.failed'));
                              }
                            }} className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50">
                              <Check className="w-4 h-4 mr-1" />
                              <span className="truncate">{t('mark_complete')}</span>
                            </Button>
                          )}
                          
                          {/* Three Dots - Ignore only */}
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="default" variant="ghost" className="h-11 w-11 p-0 flex-shrink-0">
                                <MoreVertical className="w-5 h-5" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-32">
                              <DropdownMenuItem onClick={async () => {
                                try {
                                  let endpoint;
                                  if (task.type === 'grief_support') endpoint = `${API}/grief-support/${task.data.id}/ignore`;
                                  else if (task.type === 'accident_followup') endpoint = `${API}/accident-followup/${task.data.id}/ignore`;
                                  else if (task.type === 'financial_aid') endpoint = `${API}/financial-aid-schedules/${task.data.id}/ignore`;
                                  else if (task.type === 'birthday') endpoint = `${API}/care-events/${task.data.id}/ignore`;
                                  
                                  if (endpoint) {
                                    await axios.post(endpoint);
                                    toast.success(t('toasts.ignored'));
                                    await queryClient.invalidateQueries(['dashboard']);
                                  }
                                } catch (error) {
                                  toast.error(t('toasts.failed'));
                                }
                              }}>
                                {t('ignore')}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Dashboard;