import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar as CalendarComponent } from '@/components/ui/calendar';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { ArrowLeft, Plus, Send, CheckCircle2, Calendar, Heart, Hospital, DollarSign, MoreVertical, Edit, Trash2, Check, CalendarIcon } from 'lucide-react';
import { MemberAvatar } from '@/components/MemberAvatar';
import { EngagementBadge } from '@/components/EngagementBadge';
import { EventTypeBadge } from '@/components/EventTypeBadge';
import { format } from 'date-fns/format';
import { format as formatDateFns } from 'date-fns';

// Aid type icon helper
const getAidTypeIcon = (aidType) => {
  const icons = {
    'education': '🎓',
    'medical': '🏥',
    'housing': '🏠',
    'family': '👨‍👩‍👧',
    'food': '🍚',
    'transportation': '🚗',
    'emergency': '🆘'
  };
  return icons[aidType?.toLowerCase()] || '💰';
};

// Safe date formatter
const formatDate = (dateStr, formatStr = 'dd MMM yyyy') => {
  try {
    return format(new Date(dateStr), formatStr);
  } catch (e) {
    return dateStr;
  }
};

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const MemberDetail = () => {
  const { id } = useParams();
  const { t } = useTranslation();
  const [member, setMember] = useState(null);
  const [careEvents, setCareEvents] = useState([]);
  const [griefTimeline, setGriefTimeline] = useState([]);
  const [accidentTimeline, setAccidentTimeline] = useState([]);
  const [aidSchedules, setAidSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [selectedMembers, setSelectedMembers] = useState([]);
  
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [editEventModalOpen, setEditEventModalOpen] = useState(false);
  const [eventDateOpen, setEventDateOpen] = useState(false);
  const [paymentDateOpen, setPaymentDateOpen] = useState(false);
  const [endDateOpen, setEndDateOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  
  const [newEvent, setNewEvent] = useState({
    event_type: 'regular_contact',
    event_date: new Date().toISOString().split('T')[0],
    title: '',
    description: '',
    grief_relationship: '',
    hospital_name: '',
    aid_type: 'education',
    aid_amount: '',
    // Financial aid scheduling
    schedule_frequency: 'one_time',
    schedule_start_date: new Date().toISOString().split('T')[0],
    schedule_end_date: '',
    day_of_week: 'monday',
    day_of_month: 1,
    month_of_year: 1,
    start_month: new Date().getMonth() + 1,
    start_year: new Date().getFullYear(),
    end_month: null,
    end_year: null
  });
  
  useEffect(() => {
    if (id) {
      loadMemberData();
    }
  }, [id]);
  
  const loadMemberData = async () => {
    try {
      setLoading(true);
      const timestamp = Date.now();
      const cacheHeaders = {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      };
      
      const [memberRes, eventsRes, griefRes, accidentRes, aidSchedulesRes] = await Promise.all([
        axios.get(`${API}/members/${id}?t=${timestamp}`, { headers: cacheHeaders }),
        axios.get(`${API}/care-events?member_id=${id}&t=${timestamp}`, { headers: cacheHeaders }),
        axios.get(`${API}/grief-support/member/${id}?t=${timestamp}`, { headers: cacheHeaders }),
        axios.get(`${API}/accident-followup/member/${id}?t=${timestamp}`, { headers: cacheHeaders }),
        axios.get(`${API}/financial-aid-schedules/member/${id}?t=${timestamp}`, { headers: cacheHeaders })
      ]);
      
      setMember(memberRes.data);
      setCareEvents((eventsRes.data || []).sort((a, b) => {
        // Primary sort by event_date (descending - newest first)
        const dateCompare = new Date(b.event_date) - new Date(a.event_date);
        if (dateCompare !== 0) return dateCompare;
        // Secondary sort by created_at (descending - most recent first)
        return new Date(b.created_at) - new Date(a.created_at);
      }));
      setGriefTimeline(griefRes.data);
      setAccidentTimeline(accidentRes.data);
      setAidSchedules(aidSchedulesRes.data || []);
      
      console.log('Aid schedules loaded:', aidSchedulesRes.data);
    } catch (error) {
      toast.error(t('error_messages.member_not_found'));
      console.error('Error loading member:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleAddCareEvent = async (e) => {
    e.preventDefault();
    try {
      if (newEvent.event_type === 'financial_aid') {
        if (newEvent.schedule_frequency === 'one_time') {
          // One-time aid: Create care event (aid has been given)
          const eventData = {
            member_id: id,
            campus_id: member.campus_id,
            event_type: 'financial_aid',
            event_date: newEvent.payment_date || newEvent.event_date,
            title: newEvent.title,
            description: newEvent.description,
            aid_type: newEvent.aid_type,
            aid_amount: parseFloat(newEvent.aid_amount)
          };
          await axios.post(`${API}/care-events`, eventData);
          toast.success(t('toasts.financial_aid_recorded'));
        } else {
          // Scheduled aid: Create schedule (future payments)
          let startDate, endDate;
          
          if (newEvent.schedule_frequency === 'weekly') {
            startDate = new Date().toISOString().split('T')[0];  // Use today for weekly
            endDate = newEvent.schedule_end_date || null;
          } else if (newEvent.schedule_frequency === 'monthly') {
            // Construct start_date from start_month and start_year
            const startMonth = newEvent.start_month || new Date().getMonth() + 1;
            const startYear = newEvent.start_year || new Date().getFullYear();
            startDate = `${startYear}-${String(startMonth).padStart(2, '0')}-01`;
            
            // Construct end_date from end_month and end_year if provided
            if (newEvent.end_month && newEvent.end_year) {
              endDate = `${newEvent.end_year}-${String(newEvent.end_month).padStart(2, '0')}-01`;
            } else {
              endDate = null;
            }
          } else {
            // For annually or other frequencies
            startDate = newEvent.schedule_start_date;
            endDate = newEvent.schedule_end_date || null;
          }
          
          const scheduleData = {
            member_id: id,
            campus_id: member.campus_id,
            title: newEvent.title,
            aid_type: newEvent.aid_type,
            aid_amount: parseFloat(newEvent.aid_amount),
            frequency: newEvent.schedule_frequency,
            start_date: startDate,
            end_date: endDate,
            day_of_week: newEvent.day_of_week,
            day_of_month: newEvent.day_of_month,
            month_of_year: newEvent.month_of_year,
            notes: newEvent.description
          };
          await axios.post(`${API}/financial-aid-schedules`, scheduleData);
          toast.success(t('toasts.financial_aid_schedule_created'));
        }
      } else {
        // Other event types: Create normal care event
        const eventData = {
          member_id: id,
          campus_id: member.campus_id,
          ...newEvent,
          aid_amount: newEvent.aid_amount ? parseFloat(newEvent.aid_amount) : null
        };
        await axios.post(`${API}/care-events`, eventData);
        
        if (newEvent.event_type === 'grief_loss' && newEvent.mourning_service_date) {
          toast.success(t('success_messages.grief_timeline_generated'));
        } else {
          toast.success(t('success_messages.care_event_created'));
        }
      }
      
      setEventModalOpen(false);
      setNewEvent({
        event_type: 'regular_contact',
        event_date: new Date().toISOString().split('T')[0],
        title: '',
        description: '',
        grief_relationship: '',
        mourning_service_date: '',
        hospital_name: '',
        admission_date: '',
        aid_type: 'education',
        aid_amount: '',
        schedule_frequency: 'one_time',
        payment_date: new Date().toISOString().split('T')[0],
        schedule_start_date: new Date().toISOString().split('T')[0],
        schedule_end_date: '',
        day_of_week: 'monday',
        day_of_month: 1,
        month_of_year: 1,
        start_month: new Date().getMonth() + 1,
        start_year: new Date().getFullYear(),
        end_month: null,
        end_year: null
      });
      loadMemberData();
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
    }
  };
  
  const handleDeleteEvent = async (eventId) => {
    if (!window.confirm('Delete this care event?')) return;
    try {
      await axios.delete(`${API}/care-events/${eventId}`);
      toast.success(t('toasts.event_deleted'));
      loadMemberData();
    } catch (error) {
      toast.error(t('toasts.failed_delete'));
    }
  };
  
  const sendReminder = async (eventId) => {
    try {
      const response = await axios.post(`${API}/care-events/${eventId}/send-reminder`);
      if (response.data.success) {
        toast.success(t('success_messages.reminder_sent'));
      } else {
        toast.error(t('error_messages.failed_to_send'));
      }
    } catch (error) {
      toast.error(t('error_messages.failed_to_send'));
      console.error('Error sending reminder:', error);
    }
  };
  
  const handleCompleteBirthday = async (eventId) => {
    try {
      await axios.post(`${API}/care-events/${eventId}/complete`);
      toast.success(t('toasts.birthday_marked_completed'));
      loadMemberData();
      // Trigger dashboard cache refresh by making a call
      axios.get(`${API}/dashboard/reminders`).catch(() => {});
    } catch (error) {
      toast.error(t('toasts.failed_mark_birthday'));
      console.error('Error completing birthday:', error);
    }
  };
  
  const completeGriefStage = async (stageId) => {
    try {
      await axios.post(`${API}/grief-support/${stageId}/complete`);
      toast.success(t('success_messages.stage_completed'));
      loadMemberData();
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
      console.error('Error completing stage:', error);
    }
  };
  
  if (loading) {
    return <div className="space-y-6"><Skeleton className="h-96 w-full" /></div>;
  }
  
  if (!member) {
    return <div className="text-center py-12">Member not found</div>;
  }
  
  return (
    <div className="space-y-6 max-w-full">
      {/* Header */}
      <div className="max-w-full">
        <Link to="/members">
          <Button variant="ghost" size="sm" className="mb-4 h-10">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Members
          </Button>
        </Link>
        
        <div className="flex flex-col sm:flex-row items-start gap-4 sm:gap-6 max-w-full">
          {/* Profile Photo - Larger on desktop */}
          <div className="shrink-0">
            <MemberAvatar member={member} size="xl" className="w-20 h-20 sm:w-32 sm:h-32" />
          </div>
          
          {/* Member Info */}
          <div className="flex-1 min-w-0 w-full">
            <div className="space-y-3">
              <div className="min-w-0">
                <h1 className="text-2xl sm:text-3xl font-playfair font-bold text-foreground">{member.name}</h1>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  {member.phone && (
                    <a href={`tel:${member.phone}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1">
                      📞 {member.phone}
                    </a>
                  )}
                  {member.email && (
                    <a href={`mailto:${member.email}`} className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1">
                      ✉️ {member.email}
                    </a>
                  )}
                </div>
              </div>
              
              {/* Engagement Badge & Last Contact */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                <EngagementBadge status={member.engagement_status} days={member.days_since_last_contact} />
                {member.last_contact_date && (
                  <span className="text-xs sm:text-sm text-muted-foreground">
                    {t('last_contact')}: {formatDate(member.last_contact_date, 'dd MMM yyyy')}
                  </span>
                )}
              </div>
            </div>
            
            {/* Add Care Event button - mobile friendly */}
            <Dialog open={eventModalOpen} onOpenChange={setEventModalOpen}>
              <DialogTrigger asChild>
                <Button className="bg-teal-500 hover:bg-teal-600 text-white w-full sm:w-auto mt-4 h-12 min-w-0" data-testid="add-care-event-button">
                  <Plus className="w-4 h-4 mr-2 flex-shrink-0" />
                  <span className="truncate">{t('add_care_event')}</span>
                </Button>
              </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="add-care-event-modal">
              <DialogHeader>
                <DialogTitle className="text-2xl font-playfair">{t('add_care_event')}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleAddCareEvent} className="space-y-4">
                <div>
                  <Label className="font-semibold">Event Type</Label>
                  <Select value={newEvent.event_type} onValueChange={(v) => setNewEvent({...newEvent, event_type: v})} required>
                    <SelectTrigger className="h-12" data-testid="event-type-select">
                      <SelectValue placeholder="Select event type..." />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="childbirth">👶 {t('event_types.childbirth')}</SelectItem>
                        <SelectItem value="grief_loss">💔 {t('event_types.grief_loss')}</SelectItem>
                        <SelectItem value="new_house">🏠 {t('event_types.new_house')}</SelectItem>
                        <SelectItem value="accident_illness">🚑 {t('event_types.accident_illness')}</SelectItem>
                        <SelectItem value="financial_aid">💰 {t('event_types.financial_aid')}</SelectItem>
                        <SelectItem value="regular_contact">📞 {t('event_types.regular_contact')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {newEvent.event_type !== 'financial_aid' && (
                    <div>
                      <Label className="font-semibold">Event Date</Label>
                      <Popover modal={true} open={eventDateOpen} onOpenChange={setEventDateOpen}>
                        <PopoverTrigger asChild>
                          <Button variant="outline" className="w-full h-12 justify-start text-left font-normal" type="button">
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {newEvent.event_date ? formatDateFns(new Date(newEvent.event_date), 'dd MMM yyyy') : <span className="text-muted-foreground">Select date...</span>}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="p-0 z-[9999]" side="bottom" align="start">
                          <div className="w-[280px]">
                            <CalendarComponent
                              mode="single"
                              selected={newEvent.event_date ? new Date(newEvent.event_date) : undefined}
                              onSelect={(date) => {
                                if (date) {
                                  setNewEvent({...newEvent, event_date: formatDateFns(date, 'yyyy-MM-dd')});
                                  setEventDateOpen(false);
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
                  <Textarea
                    value={newEvent.description}
                    onChange={(e) => setNewEvent({...newEvent, description: e.target.value})}
                    rows={3}
                    className="min-h-[5rem]"
                    placeholder="Additional details..."
                    data-testid="event-description-input"
                  />
                </div>
                
                {/* Title only for Financial Aid */}
                {newEvent.event_type === 'financial_aid' && (
                  <div>
                    <Label className="font-semibold">Aid Name/Title</Label>
                    <Input
                      value={newEvent.title}
                      onChange={(e) => setNewEvent({...newEvent, title: e.target.value})}
                      placeholder="e.g., Monthly Education Support"
                      className="h-12"
                      required
                      data-testid="event-title-input"
                    />
                  </div>
                )}
                
                {/* Conditional Fields */}
                {newEvent.event_type === 'grief_loss' && (
                  <div className="space-y-4 p-4 bg-purple-50 dark:bg-purple-950 rounded-lg border border-purple-200">
                    <p className="text-sm font-medium text-purple-900 dark:text-purple-100">
                      ⭐ {t('success_messages.grief_timeline_generated')}
                    </p>
                    <div>
                      <Label className="font-semibold">Relationship to Deceased</Label>
                      <Select value={newEvent.grief_relationship} onValueChange={(v) => setNewEvent({...newEvent, grief_relationship: v})} required>
                        <SelectTrigger className="h-12">
                          <SelectValue placeholder="Select relationship" />
                        </SelectTrigger>
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
                
                {newEvent.event_type === 'accident_illness' && (
                  <div className="p-4 bg-blue-50 dark:bg-blue-950 rounded-lg border border-blue-200">
                    <div>
                      <Label className="font-semibold">Hospital/Medical Facility Name</Label>
                      <Input
                        value={newEvent.hospital_name}
                        onChange={(e) => setNewEvent({...newEvent, hospital_name: e.target.value})}
                        placeholder="e.g., RSU Jakarta, Ciputra Hospital"
                        className="h-12"
                      />
                    </div>
                  </div>
                )}
                
                {newEvent.event_type === 'financial_aid' && (
                  <div className="space-y-4 p-4 bg-green-50 dark:bg-green-950 rounded-lg border border-green-200">
                    <h4 className="font-semibold text-green-900 dark:text-green-100">Financial Aid Details</h4>
                    <div className="space-y-4">
                      <div>
                        <Label className="font-semibold">Aid Type</Label>
                        <Select value={newEvent.aid_type} onValueChange={(v) => setNewEvent({...newEvent, aid_type: v})} required>
                          <SelectTrigger className="h-12"><SelectValue placeholder="Select aid type..." /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="education">{t('aid_types.education')}</SelectItem>
                            <SelectItem value="medical">{t('aid_types.medical')}</SelectItem>
                            <SelectItem value="emergency">{t('aid_types.emergency')}</SelectItem>
                            <SelectItem value="housing">{t('aid_types.housing')}</SelectItem>
                            <SelectItem value="food">{t('aid_types.food')}</SelectItem>
                            <SelectItem value="funeral_costs">{t('aid_types.funeral_costs')}</SelectItem>
                            <SelectItem value="other">{t('aid_types.other')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="font-semibold">Amount (Rp)</Label>
                        <Input
                          type="number"
                          value={newEvent.aid_amount}
                          onChange={(e) => setNewEvent({...newEvent, aid_amount: e.target.value})}
                          placeholder="1500000"
                          className="h-12"
                          required
                        />
                      </div>
                    </div>
                    
                    {/* Financial Aid Scheduling */}
                    <div className="space-y-4 border-t pt-4">
                      <h5 className="font-semibold text-green-800 dark:text-green-200">📅 Payment Type</h5>
                      <div>
                        <Label className="font-semibold">Frequency</Label>
                        <Select value={newEvent.schedule_frequency} onValueChange={(v) => setNewEvent({...newEvent, schedule_frequency: v})}>
                          <SelectTrigger className="h-12"><SelectValue placeholder="Select frequency..." /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="one_time">One-time Payment (already given)</SelectItem>
                            <SelectItem value="weekly">Weekly Schedule (future payments)</SelectItem>
                            <SelectItem value="monthly">Monthly Schedule (future payments)</SelectItem>
                            <SelectItem value="annually">Annual Schedule (future payments)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      {newEvent.schedule_frequency === 'one_time' && (
                        <div>
                          <Label className="font-semibold">Payment Date</Label>
                          <Popover modal={true} open={paymentDateOpen} onOpenChange={setPaymentDateOpen}>
                            <PopoverTrigger asChild>
                              <Button variant="outline" className="w-full h-12 justify-start text-left font-normal" type="button">
                                <CalendarIcon className="mr-2 h-4 w-4" />
                                {newEvent.payment_date ? formatDateFns(new Date(newEvent.payment_date), 'dd MMM yyyy') : <span className="text-muted-foreground">Select payment date...</span>}
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="p-0 z-[9999]" side="bottom" align="start">
                              <div className="w-[280px]">
                                <CalendarComponent
                                  mode="single"
                                  selected={newEvent.payment_date ? new Date(newEvent.payment_date) : undefined}
                                  onSelect={(date) => {
                                    if (date) {
                                      setNewEvent({...newEvent, payment_date: formatDateFns(date, 'yyyy-MM-dd')});
                                      setPaymentDateOpen(false);
                                    }
                                  }}
                                  initialFocus
                                />
                              </div>
                            </PopoverContent>
                          </Popover>
                          <p className="text-xs text-muted-foreground mt-1">Date when aid was given</p>
                        </div>
                      )}
                      
                      {newEvent.schedule_frequency === 'weekly' && (
                        <div className="grid grid-cols-2 gap-3 p-3 bg-blue-50 dark:bg-blue-950 rounded">
                          <div>
                            <Label className="font-semibold text-xs">Day of Week</Label>
                            <Select value={newEvent.day_of_week} onValueChange={(v) => setNewEvent({...newEvent, day_of_week: v})}>
                              <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="monday">Monday</SelectItem>
                                <SelectItem value="tuesday">Tuesday</SelectItem>
                                <SelectItem value="wednesday">Wednesday</SelectItem>
                                <SelectItem value="thursday">Thursday</SelectItem>
                                <SelectItem value="friday">Friday</SelectItem>
                                <SelectItem value="saturday">Saturday</SelectItem>
                                <SelectItem value="sunday">Sunday</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="font-semibold text-xs">End Date (optional)</Label>
                            <Popover modal={true} open={endDateOpen} onOpenChange={setEndDateOpen}>
                              <PopoverTrigger asChild>
                                <Button variant="outline" className="w-full h-12 justify-start text-left font-normal" type="button">
                                  <CalendarIcon className="mr-2 h-4 w-4" />
                                  {newEvent.schedule_end_date ? formatDateFns(new Date(newEvent.schedule_end_date), 'dd MMM yyyy') : <span className="text-muted-foreground">No end date</span>}
                                </Button>
                              </PopoverTrigger>
                              <PopoverContent className="p-0 z-[9999]" side="bottom" align="start">
                                <div className="w-[280px]">
                                  <CalendarComponent
                                    mode="single"
                                    selected={newEvent.schedule_end_date ? new Date(newEvent.schedule_end_date) : undefined}
                                    onSelect={(date) => {
                                      if (date) {
                                        setNewEvent({...newEvent, schedule_end_date: formatDateFns(date, 'yyyy-MM-dd')});
                                        setEndDateOpen(false);
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
                      
                      {newEvent.schedule_frequency === 'monthly' && (
                        <div className="space-y-3 p-3 bg-purple-50 dark:bg-purple-950 rounded">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <Label className="font-semibold text-xs">Start Month</Label>
                              <Select value={(newEvent.start_month || new Date().getMonth() + 1).toString()} onValueChange={(v) => setNewEvent({...newEvent, start_month: parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue /></SelectTrigger>
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
                              <Label className="font-semibold text-xs">Start Year</Label>
                              <Select value={(newEvent.start_year || new Date().getFullYear()).toString()} onValueChange={(v) => setNewEvent({...newEvent, start_year: parseInt(v)})}>
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
                            <Label className="font-semibold text-xs">Day of Month</Label>
                            <Input
                              type="number"
                              min="1"
                              max="31"
                              value={newEvent.day_of_month || ''}
                              onChange={(e) => setNewEvent({...newEvent, day_of_month: parseInt(e.target.value) || 1})}
                              placeholder="13"
                              className="h-12"
                              required
                            />
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <Label className="font-semibold text-xs">End Month (optional)</Label>
                              <Select value={(newEvent.end_month || 'none').toString()} onValueChange={(v) => setNewEvent({...newEvent, end_month: v === 'none' ? null : parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue placeholder="No end date" /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">No end date</SelectItem>
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
                              <Label className="font-semibold text-xs">End Year (optional)</Label>
                              <Select value={(newEvent.end_year || 'none').toString()} onValueChange={(v) => setNewEvent({...newEvent, end_year: v === 'none' ? null : parseInt(v)})}>
                                <SelectTrigger className="h-12"><SelectValue placeholder="No end date" /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">No end date</SelectItem>
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
                      
                      {newEvent.schedule_frequency === 'annually' && (
                        <div className="grid grid-cols-2 gap-3 p-3 bg-orange-50 dark:bg-orange-950 rounded">
                          <div>
                            <Label className="text-xs">Month of Year *</Label>
                            <Select value={newEvent.month_of_year.toString()} onValueChange={(v) => setNewEvent({...newEvent, month_of_year: parseInt(v)})}>
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
                            <Label className="text-xs">End Year (optional)</Label>
                            <Input
                              type="number"
                              min={new Date().getFullYear()}
                              max={new Date().getFullYear() + 20}
                              value={newEvent.schedule_end_date ? new Date(newEvent.schedule_end_date).getFullYear() : ''}
                              onChange={(e) => setNewEvent({...newEvent, schedule_end_date: e.target.value ? `${e.target.value}-12-31` : ''})}
                              placeholder="2030"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Action Buttons */}
                <div className="flex gap-3 pt-4">
                  <Button type="button" variant="outline" onClick={() => setEventModalOpen(false)} className="flex-1 h-12">
                    {t('cancel')}
                  </Button>
                  <Button type="submit" className="flex-1 h-12 bg-teal-500 hover:bg-teal-600 text-white font-semibold" data-testid="save-care-event-button">
                    Save Care Event
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
          </div>
        </div>
      </div>
      
      {/* Member Info Card */}
      <Card className="border-border max-w-full">
        <CardContent className="p-4 sm:p-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 sm:gap-4 max-w-full">
            {member.age && (
              <div>
                <p className="text-xs text-muted-foreground">Age</p>
                <p className="font-semibold">{member.age} years</p>
              </div>
            )}
            {member.gender && (
              <div>
                <p className="text-xs text-muted-foreground">Gender</p>
                <p className="font-semibold">{member.gender === 'M' ? 'Male' : member.gender === 'F' ? 'Female' : member.gender}</p>
              </div>
            )}
            {member.membership_status && (
              <div>
                <p className="text-xs text-muted-foreground">Membership</p>
                <p className="font-semibold">{member.membership_status}</p>
              </div>
            )}
            {member.marital_status && (
              <div>
                <p className="text-xs text-muted-foreground">Marital Status</p>
                <p className="font-semibold">{member.marital_status}</p>
              </div>
            )}
            {member.category && (
              <div>
                <p className="text-xs text-muted-foreground">Category</p>
                <p className="font-semibold">{member.category}</p>
              </div>
            )}
            {member.blood_type && (
              <div>
                <p className="text-xs text-muted-foreground">Blood Type</p>
                <p className="font-semibold">{member.blood_type}</p>
              </div>
            )}
          </div>
          {member.notes && (
            <p className="text-sm text-muted-foreground mt-4">{member.notes}</p>
          )}
        </CardContent>
      </Card>
      
      {/* Tabbed Content - Dynamic tabs based on data */}
      <Tabs defaultValue="timeline" className="w-full">
        <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex min-w-full w-max sm:w-full">
            <TabsTrigger value="timeline" data-testid="tab-timeline" className="flex-shrink-0">
              <Calendar className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Timeline</span>
            </TabsTrigger>
            {griefTimeline.length > 0 && (
              <TabsTrigger value="grief" data-testid="tab-grief" className="flex-shrink-0">
                <Heart className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Grief</span> ({griefTimeline.length})
              </TabsTrigger>
            )}
            {careEvents.filter(e => e.event_type === 'accident_illness').length > 0 && (
              <TabsTrigger value="accident" data-testid="tab-accident" className="flex-shrink-0">
                <Hospital className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Accident/Illness</span> ({careEvents.filter(e => e.event_type === 'accident_illness').length})
              </TabsTrigger>
            )}
            {(careEvents.filter(e => e.event_type === 'financial_aid').length > 0 || aidSchedules.length > 0) && (
              <TabsTrigger value="aid" data-testid="tab-aid" className="flex-shrink-0">
                <DollarSign className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Aid</span> ({careEvents.filter(e => e.event_type === 'financial_aid').length + aidSchedules.length})
              </TabsTrigger>
            )}
          </TabsList>
        </div>
        
        {/* Timeline Tab */}
        <TabsContent value="timeline" className="space-y-4">
          {/* Birthday Section - Show if within 7 days */}
          {(() => {
            const birthdayEvent = careEvents.find(e => e.event_type === 'birthday');
            if (!birthdayEvent) return null;
            
            const eventDate = new Date(birthdayEvent.event_date);
            const today = new Date();
            const thisYearBirthday = new Date(today.getFullYear(), eventDate.getMonth(), eventDate.getDate());
            const daysUntil = Math.ceil((thisYearBirthday - today) / (1000 * 60 * 60 * 24));
            
            // Show if birthday is within next 7 days, today, or overdue up to writeoff limit (7 days)
            const writeoffLimit = 7; // TODO: Get from settings
            const showBanner = (daysUntil >= -writeoffLimit && daysUntil <= 7) && !birthdayEvent.completed;
            
            if (showBanner) {
              const daysOverdue = daysUntil < 0 ? Math.abs(daysUntil) : 0;
              
              return (
                <Card className="border-amber-200 bg-amber-50/50">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
                          🎂
                        </div>
                        <div>
                          <h5 className="font-playfair font-semibold text-lg">
                            {daysUntil === 0 ? '🎉 Birthday Today!' : 
                             daysUntil > 0 ? `Upcoming Birthday (${daysUntil} days)` :
                             `⚠️ Overdue Birthday (${daysOverdue} days ago)`}
                          </h5>
                          <p className="text-sm text-muted-foreground">
                            {formatDate(birthdayEvent.event_date, 'dd MMMM yyyy')}
                          </p>
                        </div>
                      </div>
                      {birthdayEvent.completed ? (
                        <Button disabled className="bg-green-100 text-green-700">
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                          Completed
                        </Button>
                      ) : (
                        <Button 
                          onClick={() => handleCompleteBirthday(birthdayEvent.id)}
                          className="bg-amber-500 hover:bg-amber-600"
                        >
                          Mark Complete
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            }
            return null;
          })()}
          
          {/* Timeline - full width without card container */}
          {careEvents.filter(e => e.event_type !== 'birthday').length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              {t('empty_states.no_care_events')}
            </p>
          ) : (
            <div className="relative max-w-full">
                  {/* Timeline vertical line */}
                  <div className="absolute left-6 sm:left-7 top-12 bottom-0 w-0.5 bg-border"></div>
                  
                  {careEvents.filter(e => e.event_type !== 'birthday').map((event, idx) => {
                    const isIgnored = event.ignored === true;
                    const isCompleted = event.completed === true;
                    
                    // Determine dot color based on event type
                    let dotColor = 'bg-teal-500'; // Default: regular contact, general
                    if (event.event_type === 'birthday' || event.event_type === 'childbirth' || event.event_type === 'new_house') {
                      dotColor = 'bg-amber-500'; // Celebrations
                    } else if (event.event_type === 'grief_loss' || event.event_type === 'accident_illness' || event.event_type === 'hospital_visit') {
                      dotColor = 'bg-pink-500'; // Care/follow-ups
                    } else if (event.event_type === 'financial_aid') {
                      dotColor = 'bg-purple-500'; // Special/aid
                    }
                    
                    // Determine border color for card
                    let borderClass = 'card-border-left-teal';
                    if (event.event_type === 'birthday' || event.event_type === 'childbirth' || event.event_type === 'new_house') {
                      borderClass = 'card-border-left-amber';
                    } else if (event.event_type === 'grief_loss' || event.event_type === 'accident_illness' || event.event_type === 'hospital_visit') {
                      borderClass = 'card-border-left-pink';
                    } else if (event.event_type === 'financial_aid') {
                      borderClass = 'card-border-left-purple';
                    }
                    
                    return (
                    <div key={event.id} className={`flex gap-3 sm:gap-4 pb-6 relative`} data-testid={`care-event-${event.id}`}>
                      
                      {/* Timeline date marker with colored dot - always full opacity */}
                      <div className="flex flex-col items-center shrink-0 w-12 sm:w-16">
                        {/* Date circle */}
                        <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-white border-2 border-gray-200 shadow-md flex flex-col items-center justify-center relative z-10">
                          <div className="text-sm sm:text-base font-bold leading-none">{formatDate(event.event_date, 'dd')}</div>
                          <div className="text-[9px] sm:text-[10px] leading-none uppercase opacity-70 mt-0.5">{formatDate(event.event_date, 'MMM')}</div>
                        </div>
                        {/* Colored dot indicator below date - always vibrant */}
                        <div className={`w-3 h-3 sm:w-4 sm:h-4 rounded-full ${dotColor} border-2 border-background shadow-sm mt-1 relative z-10`}></div>
                      </div>
                      
                      {/* Event content card - apply opacity here if completed/ignored */}
                      <Card className={`flex-1 ${borderClass} shadow-sm hover:shadow-md transition-all min-w-0 card ${isIgnored || isCompleted ? 'opacity-60' : ''}`}>
                        <CardContent className="p-3 sm:p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex flex-wrap items-center gap-2 mb-2">
                                <EventTypeBadge type={event.event_type} />
                                {/* Status badges inline with event type */}
                                {isCompleted && (
                                  <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded flex items-center gap-1">
                                    <CheckCircle2 className="w-3 h-3" />
                                    Completed
                                  </span>
                                )}
                                {isIgnored && !isCompleted && (
                                  <span className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded">Ignored</span>
                                )}
                              </div>
                              <h5 className="font-playfair font-semibold text-sm sm:text-base text-foreground mb-2">{event.title}</h5>
                              {event.description && (
                                <p className="text-sm whitespace-pre-line font-bold text-foreground mb-2">
                                  {event.description}
                                </p>
                              )}
                              {event.grief_relationship && (
                                <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                                  Relationship: {event.grief_relationship}
                                </p>
                              )}
                              {event.hospital_name && event.hospital_name !== 'N/A' && event.hospital_name !== 'null' && event.hospital_name !== 'NULL' && (
                                <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                                  Hospital: {event.hospital_name}
                                </p>
                              )}
                              {event.aid_amount && (
                                <p className="text-sm text-green-700 font-medium mt-2">
                                  {event.aid_type && `${event.aid_type} - `}Rp {event.aid_amount.toLocaleString('id-ID')}
                                </p>
                              )}
                            </div>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost" className="min-h-[44px] min-w-[44px] shrink-0">
                                  <MoreVertical className="w-5 h-5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleDeleteEvent(event.id)} className="text-red-600">
                                  <Trash2 className="w-4 h-4 mr-2" />Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                    );
                  })}
            </div>
          )}
        </TabsContent>
        
        {/* Grief Support Tab */}
        <TabsContent value="grief" className="space-y-4">
          {careEvents.filter(e => e.event_type === 'grief_loss').length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No grief/loss events recorded.
            </p>
          ) : (
            careEvents.filter(e => e.event_type === 'grief_loss').map(event => (
                  <div key={event.id} className="space-y-4 mb-6 p-4 border border-pink-200 bg-pink-50 rounded-lg shadow-sm">
                    <div>
                      <h4 className="font-semibold">💔 {event.title || 'Grief/Loss Event'}</h4>
                      <p className="text-sm text-muted-foreground">
                        Date: {formatDate(event.event_date, 'dd MMM yyyy')}
                      </p>
                      {event.grief_relationship && (
                        <p className="text-sm text-muted-foreground">
                          Relationship: {event.grief_relationship}
                        </p>
                      )}
                      {event.description && (
                        <p className="text-sm mt-2">{event.description}</p>
                      )}
                    </div>
                    
                    {/* Grief Timeline within each grief event */}
                    <div className="mt-4">
                      <h5 className="text-sm font-semibold mb-3">Support Timeline:</h5>
                      <div className="space-y-3">
                        {griefTimeline.filter(s => s.care_event_id === event.id).map((stage, index) => {
                          const isIgnored = stage.ignored === true;
                          return (
                          <div key={stage.id} className={`flex items-center gap-3 p-2 bg-pink-50 rounded relative ${isIgnored ? 'opacity-60' : ''}`}>
                            {isIgnored && (
                              <div className="absolute top-1 right-1">
                                <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">Ignored</span>
                              </div>
                            )}
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                              stage.completed ? 'bg-pink-500' : 'bg-pink-200'
                            }`}>
                              {stage.completed ? (
                                <span className="text-white text-xs">✓</span>
                              ) : (
                                <span className="text-pink-700 text-xs font-bold">{index + 1}</span>
                              )}
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-medium">
                                {t(`grief_stages.${stage.stage}`)}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {formatDate(stage.scheduled_date, 'dd MMM')}
                              </p>
                            </div>
                            {(stage.completed || isIgnored) && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button size="sm" variant="ghost">
                                    <MoreVertical className="w-4 h-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      await axios.post(`${API}/grief-support/${stage.id}/undo`);
                                      toast.success(t('toasts.action_undone'));
                                      loadMemberData(); // Reload to remove timeline event and update tabs
                                    } catch (error) {
                                      toast.error(t('toasts.failed_undo'));
                                    }
                                  }}>
                                    Undo
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            )}
                            {!stage.completed && !isIgnored && (
                              <div className="flex gap-1">
                                <Button size="sm" variant="outline" className="min-h-[44px]" onClick={async () => {
                                  try {
                                    await axios.post(`${API}/grief-support/${stage.id}/complete`);
                                    toast.success(t('success_messages.stage_completed'));
                                    loadMemberData(); // Reload to show timeline event
                                  } catch (error) {
                                    toast.error(t('toasts.failed'));
                                  }
                                }}>
                                  Mark Complete
                                </Button>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button size="sm" variant="ghost">
                                      <MoreVertical className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={async () => {
                                      try {
                                        await axios.post(`${API}/grief-support/${stage.id}/ignore`);
                                        toast.success('Grief stage ignored');
                                        // Update local state instead of full reload
                                        setGriefTimeline(prev => prev.map(s => 
                                          s.id === stage.id ? {...s, ignored: true} : s
                                        ));
                                      } catch (error) {
                                        toast.error('Failed to ignore');
                                      }
                                    }}>
                                      Ignore
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                            )}
                          </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ))
          )}
        </TabsContent>
        
        {/* Accident/Illness Tab */}
        <TabsContent value="accident">
          {careEvents.filter(e => e.event_type === 'accident_illness').length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No accident/illness visits recorded.</p>
          ) : (
            careEvents.filter(e => e.event_type === 'accident_illness').map(event => (
                  <div key={event.id} className="space-y-4 mb-6 p-4 border border-blue-200 bg-blue-50 rounded-lg shadow-sm relative">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h4 className="font-semibold text-lg mb-1">🏥 {event.description || event.title || 'Accident/Illness Visit'}</h4>
                        <p className="text-sm text-muted-foreground">
                          Date: {formatDate(event.event_date, 'dd MMM yyyy')}
                        </p>
                        {event.hospital_name && event.hospital_name !== 'N/A' && event.hospital_name !== 'null' && event.hospital_name !== 'NULL' && (
                          <p className="text-sm text-muted-foreground">
                            Facility: {event.hospital_name}
                          </p>
                        )}
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="ghost">
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleDeleteEvent(event.id)} className="text-red-600">
                            <Trash2 className="w-4 h-4 mr-2" />Delete Event
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    
                    {/* Follow-up Timeline within each accident record */}
                    <div className="mt-4">
                      <h5 className="text-sm font-semibold mb-3">Follow-up Schedule:</h5>
                      <div className="space-y-3">
                        {accidentTimeline.filter(t => t.care_event_id === event.id).map((stage, index) => {
                          const isIgnored = stage.ignored === true;
                          return (
                          <div key={stage.id} className={`flex items-center gap-3 p-2 bg-blue-50 rounded relative ${isIgnored ? 'opacity-60' : ''}`}>
                            {isIgnored && (
                              <div className="absolute top-1 right-1">
                                <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">Ignored</span>
                              </div>
                            )}
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                              stage.completed ? 'bg-blue-500' : 'bg-blue-200'
                            }`}>
                              {stage.completed ? (
                                <span className="text-white text-xs">✓</span>
                              ) : (
                                <span className="text-blue-700 text-xs font-bold">{index + 1}</span>
                              )}
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-medium">
                                {stage.stage === 'first_followup' ? 'First Follow-up' :
                                 stage.stage === 'second_followup' ? 'Second Follow-up' : 'Final Follow-up'}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {formatDate(stage.scheduled_date, 'dd MMM')}
                              </p>
                            </div>
                            {(stage.completed || isIgnored) && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button size="sm" variant="ghost">
                                    <MoreVertical className="w-4 h-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      await axios.post(`${API}/accident-followup/${stage.id}/undo`);
                                      toast.success(t('toasts.action_undone'));
                                      loadMemberData(); // Reload to remove timeline event and update tabs
                                    } catch (error) {
                                      toast.error(t('toasts.failed_undo'));
                                    }
                                  }}>
                                    Undo
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            )}
                            {!stage.completed && !isIgnored && (
                              <div className="flex gap-1">
                                <Button size="sm" variant="outline" className="min-h-[44px]" onClick={async () => {
                                  try {
                                    await axios.post(`${API}/accident-followup/${stage.id}/complete`);
                                    toast.success('Follow-up completed');
                                    loadMemberData(); // Reload to show timeline event
                                  } catch (error) {
                                    toast.error(t('toasts.failed'));
                                  }
                                }}>
                                  Mark Complete
                                </Button>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button size="sm" variant="ghost">
                                      <MoreVertical className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={async () => {
                                      try {
                                        await axios.post(`${API}/accident-followup/${stage.id}/ignore`);
                                        toast.success('Follow-up ignored');
                                        // Update local state
                                        setAccidentTimeline(prev => prev.map(s => 
                                          s.id === stage.id ? {...s, ignored: true} : s
                                        ));
                                      } catch (error) {
                                        toast.error('Failed to ignore');
                                      }
                                    }}>
                                      Ignore
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                            )}
                          </div>
                          );
                        })}
                      </div>
                    </div>
                    
                    {event.visitation_log && event.visitation_log.length > 0 && (
                      <div className="space-y-2 mt-4">
                        <h5 className="text-sm font-medium">Visitation Log:</h5>
                        {event.visitation_log.map((log, idx) => (
                          <div key={idx} className="text-sm bg-muted/30 p-3 rounded">
                            <p className="font-medium">{log.visitor_name} - {formatDate(log.visit_date, 'dd MMM yyyy')}</p>
                            <p className="text-muted-foreground">{log.notes}</p>
                            {log.prayer_offered && <p className="text-xs text-primary-600 mt-1">✓ Prayer offered</p>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
          )}
        </TabsContent>
        
        {/* Financial Aid Tab */}
        <TabsContent value="aid">
          <Card>
            <CardContent className="p-6">
              {/* Past Financial Aid (One-time aid given) */}
              <div className="space-y-4">
                <h4 className="font-semibold text-foreground">Past Financial Aid Given</h4>
                {careEvents.filter(e => e.event_type === 'financial_aid').length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4">No financial aid recorded.</p>
                ) : (
                  <div className="space-y-3">
                    {careEvents.filter(e => e.event_type === 'financial_aid').map(event => (
                      <div key={event.id} className={`p-4 rounded-lg border relative hover:shadow-lg transition-all ${event.ignored ? 'bg-gray-50 border-gray-300 card-border-left-gray opacity-70' : 'bg-purple-50 border-purple-200 card-border-left-purple'}`}>
                        {/* Only show "Ignored" badge, remove Given/Completed badges */}
                        {event.ignored && (
                          <span className="absolute top-3 right-14 px-2 py-1 bg-gray-400 text-white text-xs font-semibold rounded shadow-sm z-10">
                            Ignored
                          </span>
                        )}
                        
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 flex-1 min-w-0">
                            {/* Aid Type Icon */}
                            <div className="text-3xl flex-shrink-0">
                              {getAidTypeIcon(event.aid_type)}
                            </div>
                            
                            <div className="flex-1 min-w-0">
                              {/* Title if exists */}
                              {event.title && (
                                <p className="font-semibold text-base text-foreground mb-1">
                                  {event.title}
                                </p>
                              )}
                              {/* Amount - Hero */}
                              <p className="text-lg font-bold text-foreground">
                                Rp {event.aid_amount?.toLocaleString('id-ID')}
                              </p>
                              {/* Aid Type */}
                              <p className="text-xs text-muted-foreground mt-1">
                                {event.aid_type?.charAt(0).toUpperCase() + event.aid_type?.slice(1)}
                              </p>
                              {/* Date */}
                              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                                📅 {formatDate(event.event_date, 'dd MMM yyyy')}
                              </p>
                              {/* Notes */}
                              {event.aid_notes && (
                                <p className="text-xs text-muted-foreground mt-2 italic">{event.aid_notes}</p>
                              )}
                            </div>
                          </div>
                          
                          {/* Three Dots - Top Right */}
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="sm" variant="ghost" className="h-8 w-8 p-0 flex-shrink-0">
                                <MoreVertical className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-32">
                              <DropdownMenuItem onClick={() => handleDeleteEvent(event.id)} className="text-red-600">
                                <Trash2 className="w-4 h-4 mr-2" />Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Scheduled Financial Aid (Future payments) */}
                <div className="border-t pt-4">
                  <h4 className="font-semibold text-foreground">Upcoming Scheduled Payments</h4>
                  {aidSchedules.filter(s => s.is_active !== false).length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4">No scheduled aid.</p>
                  ) : (
                    <div className="space-y-4 mt-3">
                      {aidSchedules.filter(s => s.is_active !== false).slice(0, 5).map(schedule => {
                        const isIgnored = schedule.ignored === true;
                        return (
                        <div key={schedule.id} className={`p-4 rounded-lg border relative hover:shadow-lg transition-all ${isIgnored ? 'bg-gray-50 border-gray-300 card-border-left-gray opacity-70' : 'bg-purple-50 border-purple-200 card-border-left-purple'}`}>
                          {/* Only show Ignored badge */}
                          {isIgnored && (
                            <span className="absolute top-3 right-14 px-2 py-1 bg-gray-400 text-white text-xs font-semibold rounded shadow-sm z-10">
                              Ignored
                            </span>
                          )}
                          
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3 flex-1 min-w-0">
                              {/* Aid Type Icon */}
                              <div className="text-3xl flex-shrink-0">
                                {getAidTypeIcon(schedule.aid_type)}
                              </div>
                              
                              <div className="flex-1 min-w-0">
                                {/* Title */}
                                {schedule.title && (
                                  <p className="font-semibold text-base text-foreground mb-1">
                                    {schedule.title}
                                  </p>
                                )}
                                {/* Amount - Hero */}
                                <p className="text-lg font-bold text-foreground">
                                  Rp {schedule.aid_amount?.toLocaleString('id-ID')}
                                </p>
                                {/* Frequency + Aid Type */}
                                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                                  <span className="inline-flex items-center gap-1">
                                    🔄 {schedule.frequency?.charAt(0).toUpperCase() + schedule.frequency?.slice(1)}
                                  </span>
                                  <span>•</span>
                                  <span>{schedule.aid_type?.charAt(0).toUpperCase() + schedule.aid_type?.slice(1)}</span>
                                </p>
                                {/* Dates */}
                                <p className="text-xs text-muted-foreground mt-1">
                                  📅 Next: {formatDate(schedule.next_occurrence, 'dd MMM yyyy')}
                                </p>
                              </div>
                            </div>
                            
                            {/* Three Dots - Top Right */}
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost" className="h-8 w-8 p-0 flex-shrink-0">
                                  <MoreVertical className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-40">
                                <DropdownMenuItem onClick={async () => {
                                  if (window.confirm('Mark this scheduled payment as distributed?')) {
                                    try {
                                      await axios.post(`${API}/financial-aid-schedules/${schedule.id}/mark-distributed`);
                                      toast.success('Payment distributed! Schedule advanced to next occurrence.');
                                      loadMemberData();
                                    } catch (error) {
                                      toast.error('Failed to mark payment');
                                    }
                                  }
                                }} className="text-green-600">
                                  <Check className="w-4 h-4 mr-2" />
                                  Distributed
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={async () => {
                                  if (window.confirm('Stop this aid schedule? (Ignored history will be preserved)')) {
                                    try {
                                      await axios.post(`${API}/financial-aid-schedules/${schedule.id}/stop`);
                                      toast.success('Schedule stopped');
                                      loadMemberData();
                                    } catch (error) {
                                      toast.error('Failed to stop schedule');
                                    }
                                  }
                                }} className="text-red-600">
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  Stop Schedule
                                </DropdownMenuItem>
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      const response = await axios.post(`${API}/financial-aid-schedules/${schedule.id}/ignore`);
                                      toast.success(`Payment ignored! Next payment: ${response.data.next_occurrence}`);
                                      loadMemberData();
                                    } catch (error) {
                                      toast.error('Failed to ignore');
                                    }
                                  }}>
                                    Ignore This Payment
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                
                {/* Ignored/Missed Payment Schedule */}
                {aidSchedules.some(s => s.ignored_occurrences && s.ignored_occurrences.length > 0) && (
                  <div className="border-t pt-4">
                    <h4 className="font-semibold text-foreground mb-3">Ignored/Missed Payments</h4>
                    <div className="space-y-2">
                      {aidSchedules.filter(s => s.ignored_occurrences && s.ignored_occurrences.length > 0).map(schedule => (
                        <div key={`ignored-${schedule.id}`} className="p-3 bg-gray-100 rounded border border-gray-300 opacity-70">
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <p className="font-medium text-sm">{schedule.title}</p>
                              <div className="text-xs text-muted-foreground mt-1 space-y-1">
                                {schedule.ignored_occurrences.map((date, idx) => (
                                  <div key={idx} className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                      <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded">Ignored</span>
                                      <span>{formatDate(date, 'dd MMM yyyy')}</span>
                                    </div>
                                    <Button 
                                      size="sm" 
                                      variant="ghost" 
                                      className="h-6 px-2"
                                      onClick={async () => {
                                        if (window.confirm(`Remove this ignored occurrence (${formatDate(date, 'dd MMM yyyy')})?`)) {
                                          try {
                                            await axios.delete(`${API}/financial-aid-schedules/${schedule.id}/ignored-occurrence/${date}`);
                                            toast.success('Ignored occurrence removed');
                                            loadMemberData();
                                          } catch (error) {
                                            toast.error('Failed to remove');
                                          }
                                        }
                                      }}
                                    >
                                      <Trash2 className="w-3 h-3 text-red-600" />
                                    </Button>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost">
                                  <MoreVertical className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={async () => {
                                  if (window.confirm('Delete this entire financial aid schedule and all its history?')) {
                                    try {
                                      await axios.delete(`${API}/financial-aid-schedules/${schedule.id}`);
                                      toast.success('Schedule deleted');
                                      loadMemberData();
                                    } catch (error) {
                                      toast.error(t('toasts.failed_delete'));
                                    }
                                  }
                                }} className="text-red-600">
                                  <Trash2 className="w-4 h-4 mr-2" />Delete Entire Schedule
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                
                {/* Total Summary */}
                <div className="pt-4 border-t">
                  <p className="text-right font-semibold text-foreground">
                    Total Given: Rp {careEvents
                      .filter(e => e.event_type === 'financial_aid' && !e.ignored && e.completed !== false)
                      .reduce((sum, e) => sum + (e.aid_amount || 0), 0)
                      .toLocaleString('id-ID')}
                  </p>
                  <p className="text-right text-xs text-muted-foreground mt-1">
                    (Excludes ignored and pending payments)
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MemberDetail;