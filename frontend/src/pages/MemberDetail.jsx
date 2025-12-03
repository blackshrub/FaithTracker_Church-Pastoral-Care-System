/**
 * Member Detail Page - Comprehensive member profile and care history
 * Displays member information, care events timeline, grief/accident follow-ups
 * Manages all care event operations with complete accountability tracking
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MemberDetailSkeleton } from '@/components/skeletons';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { ConfirmDialog } from '@/components/ConfirmDialog';
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
import { MemberProfileHeader, TimelineEventCard } from '@/components/member';
import { formatDate, getTodayLocal, formatDateToLocalTimezone } from '@/lib/dateUtils';
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

// formatDate is imported from @/lib/dateUtils

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const MemberDetail = () => {
  const { id } = useParams();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  
  // React Query for member data
  const { data: memberData, isLoading } = useQuery({
    queryKey: ['member', id],
    queryFn: async () => {
      const timestamp = Date.now();
      const cacheHeaders = {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      };
      
      const [memberRes, eventsRes, griefRes, accidentRes, aidSchedulesRes] = await Promise.all([
        api.get(`/members/${id}?t=${timestamp}`, { headers: cacheHeaders }),
        api.get(`/care-events?member_id=${id}&t=${timestamp}`, { headers: cacheHeaders }),
        api.get(`/grief-support/member/${id}?t=${timestamp}`, { headers: cacheHeaders }),
        api.get(`/accident-followup/member/${id}?t=${timestamp}`, { headers: cacheHeaders }),
        api.get(`/financial-aid-schedules/member/${id}?t=${timestamp}`, { headers: cacheHeaders })
      ]);
      
      const sortedEvents = (eventsRes.data || []).sort((a, b) => {
        const dateCompare = new Date(b.event_date) - new Date(a.event_date);
        if (dateCompare !== 0) return dateCompare;
        return new Date(b.created_at) - new Date(a.created_at);
      });
      
      return {
        member: memberRes.data,
        careEvents: sortedEvents,
        griefTimeline: griefRes.data,
        accidentTimeline: accidentRes.data,
        aidSchedules: aidSchedulesRes.data || []
      };
    },
    enabled: !!id,
    onError: (error) => {
      if (error.response?.status === 404) {
        toast.error(t('error_messages.member_not_found'));
      }
    }
  });
  
  // Extract data with defaults
  const member = memberData?.member || null;
  const careEvents = memberData?.careEvents || [];
  const griefTimeline = memberData?.griefTimeline || [];
  const accidentTimeline = memberData?.accidentTimeline || [];
  const aidSchedules = memberData?.aidSchedules || [];
  
  // UI state
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
    event_date: getTodayLocal(),
    title: '',
    description: '',
    grief_relationship: '',
    hospital_name: '',
    aid_type: 'education',
    aid_amount: '',
    // Financial aid scheduling
    schedule_frequency: 'one_time',
    schedule_start_date: getTodayLocal(),
    schedule_end_date: '',
    day_of_week: 'monday',
    day_of_month: 1,
    month_of_year: 1,
    start_month: new Date().getMonth() + 1,
    start_year: new Date().getFullYear(),
    end_month: null,
    end_year: null
  });

  const [additionalVisitForm, setAdditionalVisitForm] = useState({});
  const [additionalVisit, setAdditionalVisit] = useState({
    visit_date: getTodayLocal(),
    visit_type: 'Phone Call',
    notes: ''
  });
  
  const toggleAdditionalForm = (eventId) => {
    setAdditionalVisitForm(prev => ({
      ...prev,
      [eventId]: !prev[eventId]
    }));
  };
  
  const logAdditionalVisit = async (parentEvent) => {
    try {
      await api.post(`/care-events/${parentEvent.id}/additional-visit`, {
        visit_date: additionalVisit.visit_date,
        visit_type: additionalVisit.visit_type,
        notes: additionalVisit.notes
      });
      toast.success('Additional visit logged successfully');
      setAdditionalVisitForm({});
      setAdditionalVisit({
        visit_date: getTodayLocal(),
        visit_type: 'Phone Call',
        notes: ''
      });
      queryClient.invalidateQueries(['member', id]);
    } catch (error) {
      console.error('Full error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Unknown error';
      toast.error('Failed to log visit: ' + errorMsg);
    }
  };

  // Confirmation dialog state
  const [confirmDialog, setConfirmDialog] = useState({
    open: false,
    title: '',
    description: '',
    onConfirm: () => {}
  });
  
  const showConfirm = (title, description, onConfirm) => {
    setConfirmDialog({
      open: true,
      title,
      description,
      onConfirm
    });
  };
  
  const closeConfirm = () => {
    setConfirmDialog({
      open: false,
      title: '',
      description: '',
      onConfirm: () => {}
    });
  };

  
  // The useQuery automatically fetches when id changes, no need for useEffect
  
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
          await api.post(`/care-events`, eventData);
          toast.success(t('toasts.financial_aid_recorded'));
        } else {
          // Scheduled aid: Create schedule (future payments)
          let startDate, endDate;
          
          if (newEvent.schedule_frequency === 'weekly') {
            startDate = getTodayLocal();  // Use today for weekly
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
          await api.post(`/financial-aid-schedules`, scheduleData);
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
        await api.post(`/care-events`, eventData);
        
        if (newEvent.event_type === 'grief_loss' && newEvent.mourning_service_date) {
          toast.success(t('success_messages.grief_timeline_generated'));
        } else {
          toast.success(t('success_messages.care_event_created'));
        }
      }
      
      setEventModalOpen(false);
      setNewEvent({
        event_type: 'regular_contact',
        event_date: getTodayLocal(),
        title: '',
        description: '',
        grief_relationship: '',
        mourning_service_date: '',
        hospital_name: '',
        admission_date: '',
        aid_type: 'education',
        aid_amount: '',
        schedule_frequency: 'one_time',
        payment_date: getTodayLocal(),
        schedule_start_date: getTodayLocal(),
        schedule_end_date: '',
        day_of_week: 'monday',
        day_of_month: 1,
        month_of_year: 1,
        start_month: new Date().getMonth() + 1,
        start_year: new Date().getFullYear(),
        end_month: null,
        end_year: null
      });
      queryClient.invalidateQueries(['member', id]);
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
    }
  };
  
  const handleDeleteEvent = async (eventId) => {
    showConfirm(
      'Delete Care Event',
      'Are you sure you want to delete this care event? This will also delete all related follow-up stages and activity logs.',
      async () => {
        try {
          await api.delete(`/care-events/${eventId}`);
          toast.success(t('toasts.event_deleted'));
          queryClient.invalidateQueries(['member', id]);
          closeConfirm();
        } catch (error) {
          toast.error(t('toasts.failed_delete'));
          closeConfirm();
        }
      }
    );
  };
  
  const sendReminder = async (eventId) => {
    try {
      const response = await api.post(`/care-events/${eventId}/send-reminder`);
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
      await api.post(`/care-events/${eventId}/complete`);
      toast.success(t('toasts.birthday_marked_completed'));
      queryClient.invalidateQueries(['member', id]);
      // Trigger dashboard cache refresh by making a call
      api.get(`/dashboard/reminders`).catch(() => {});
    } catch (error) {
      toast.error(t('toasts.failed_mark_birthday'));
      console.error('Error completing birthday:', error);
    }
  };
  
  const completeGriefStage = async (stageId) => {
    try {
      await api.post(`/grief-support/${stageId}/complete`);
      toast.success(t('success_messages.stage_completed'));
      queryClient.invalidateQueries(['member', id]);
    } catch (error) {
      toast.error(t('error_messages.failed_to_save'));
      console.error('Error completing stage:', error);
    }
  };
  
  if (isLoading) {
    return <MemberDetailSkeleton />;
  }
  
  if (!member) {
    return <div className="text-center py-12">Member not found</div>;
  }
  
  return (
    <div className="space-y-6 max-w-full">
      {/* Header */}
      <MemberProfileHeader
        member={member}
        onAddCareEvent={() => setEventModalOpen(true)}
      />

      {/* Add Care Event Dialog */}
      <Dialog open={eventModalOpen} onOpenChange={setEventModalOpen}>
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
            {careEvents.filter(e => e.event_type === 'accident_illness' && !e.accident_stage_id && !e.care_event_id).length > 0 && (
              <TabsTrigger value="accident" data-testid="tab-accident" className="flex-shrink-0">
                <Hospital className="w-4 h-4 sm:mr-2" /><span className="hidden sm:inline">Accident/Illness</span> ({careEvents.filter(e => e.event_type === 'accident_illness' && !e.accident_stage_id && !e.care_event_id).length})
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
                  
                  {careEvents.filter(e => e.event_type !== 'birthday').map((event) => (
                    <TimelineEventCard
                      key={event.id}
                      event={event}
                      onDelete={handleDeleteEvent}
                    />
                  ))}
            </div>
          )}
        </TabsContent>
        
        {/* Grief Support Tab */}
        <TabsContent value="grief" className="space-y-4">
          {careEvents.filter(e => e.event_type === 'grief_loss' && !e.grief_stage_id).length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No grief/loss events recorded.
            </p>
          ) : (
            careEvents.filter(e => e.event_type === 'grief_loss' && !e.grief_stage_id && e.followup_type !== 'additional').map(event => (
                  <div key={event.id} className="space-y-4 mb-6 p-4 border border-pink-200 bg-pink-50 rounded-lg shadow-sm">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-semibold">💔 {event.title || 'Grief/Loss Event'}</h4>
                        <p className="text-sm text-muted-foreground">
                          Date: {formatDate(event.event_date, 'dd MMM yyyy')}
                        </p>
                        {event.grief_relationship && (
                          <p className="text-sm text-muted-foreground">
                            Relationship: {event.grief_relationship.charAt(0).toUpperCase() + event.grief_relationship.slice(1)}
                          </p>
                        )}
                        {event.description && (
                          <p className="text-sm mt-2">{event.description}</p>
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
                    
                    {/* Grief Timeline within each grief event */}
                    <div className="mt-4">
                      <h5 className="text-sm font-semibold mb-3">Support Timeline:</h5>
                      <div className="space-y-3">
                        {griefTimeline.filter(s => s.care_event_id === event.id).map((stage, index) => {
                          const isIgnored = stage.ignored === true;
                          const isCompleted = stage.completed === true;
                          return (
                          <div key={stage.id} className={`flex items-center gap-3 p-2 bg-pink-50 rounded ${isIgnored ? 'opacity-60' : ''}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                              isCompleted ? 'bg-pink-500' : 'bg-pink-200'
                            }`}>
                              {isCompleted ? (
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
                            
                            {/* Show button for all states */}
                            <div className="flex gap-1">
                              {isCompleted && (
                                <Button size="sm" variant="outline" className="min-h-[44px] bg-green-50 text-green-700 border-green-200" disabled>
                                  Completed
                                </Button>
                              )}
                              {isIgnored && (
                                <Button size="sm" variant="outline" className="min-h-[44px] bg-gray-100 text-gray-500 border-gray-300" disabled>
                                  Ignored
                                </Button>
                              )}
                              {!isCompleted && !isIgnored && (
                                <Button size="sm" variant="outline" className="min-h-[44px]" onClick={async () => {
                                  try {
                                    await api.post(`/grief-support/${stage.id}/complete`);
                                    toast.success(t('success_messages.stage_completed'));
                                    queryClient.invalidateQueries(['member', id]);
                                  } catch (error) {
                                    toast.error(t('toasts.failed'));
                                  }
                                }}>
                                  Mark Complete
                                </Button>
                              )}
                              
                              {/* Three dots menu */}
                              {(isCompleted || isIgnored) && (
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button size="sm" variant="ghost">
                                      <MoreVertical className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={async () => {
                                      try {
                                        await api.post(`/grief-support/${stage.id}/undo`);
                                        toast.success(t('toasts.action_undone'));
                                        queryClient.invalidateQueries(['member', id]);
                                      } catch (error) {
                                        toast.error(t('toasts.failed_undo'));
                                      }
                                    }}>
                                      Undo
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              )}
                              
                              {!isCompleted && !isIgnored && (
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button size="sm" variant="ghost">
                                      <MoreVertical className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={async () => {
                                      try {
                                        await api.post(`/grief-support/${stage.id}/ignore`);
                                        toast.success('Grief stage ignored');
                                        queryClient.invalidateQueries(['member', id]);
                                      } catch (error) {
                                        toast.error('Failed to ignore');
                                        console.error('Error ignoring grief stage:', error);
                                      }
                                    }}>
                                      Ignore
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              )}
                            </div>
                          </div>
                          );
                        })}
                      </div>

                      
                      {/* Button to log additional visit */}
                      
                      {/* Display additional visits - Simplified approach */}
                      <div className="mt-4">
                        <h5 className="text-sm font-semibold mb-3 text-gray-700">📝 Additional Visits:</h5>
                        {careEvents
                          .filter(e => e.care_event_id === event.id && e.followup_type === "additional")
                          .map((visit) => (
                            <div key={visit.id} className="flex items-start gap-3 p-2 bg-gray-50 rounded border border-gray-200 mb-2">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center bg-gray-300">
                                <span className="text-white text-xs">✓</span>
                              </div>
                              <div className="flex-1">
                                <p className="text-sm font-medium text-gray-800">
                                  {visit.title}
                                </p>
                                <p className="text-xs text-gray-600">
                                  {formatDate(visit.event_date, 'dd MMM yyyy')}
                                </p>
                                {visit.description && (
                                  <p className="text-xs text-gray-600 mt-1">{visit.description}</p>
                                )}
                                {visit.created_by_user_name && (
                                  <p className="text-xs text-gray-500 mt-1">
                                    By: {visit.created_by_user_name}
                                  </p>
                                )}
                              </div>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-red-500 hover:text-red-700"
                                onClick={() => {
                                  showConfirm(
                                    'Delete Additional Visit',
                                    'Are you sure you want to delete this additional visit? This action cannot be undone.',
                                    async () => {
                                      try {
                                        await api.delete(`/care-events/${visit.id}`);
                                        toast.success('Visit deleted');
                                        queryClient.invalidateQueries(['member', id]);
                                        closeConfirm();
                                      } catch (error) {
                                        toast.error('Failed to delete');
                                        closeConfirm();
                                      }
                                    }
                                  );
                                }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          ))}
                        {careEvents.filter(e => e.care_event_id === event.id && e.followup_type === "additional").length === 0 && (
                          <p className="text-xs text-gray-500 italic mb-3">No additional visits yet</p>
                        )}
                        
                        {/* Button to log additional visit - now at bottom */}
                        {!additionalVisitForm[event.id] ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-full gap-2 border-dashed"
                            onClick={() => toggleAdditionalForm(event.id)}
                          >
                            <Plus className="w-4 h-4" />
                            Log Additional Visit
                          </Button>
                        ) : (
                          <div className="space-y-3 p-3 bg-white rounded border border-pink-300">
                            <h6 className="font-medium text-sm">Log Additional Visit</h6>
                            <div>
                              <Label className="text-xs">Visit Date</Label>
                              <Input
                                type="date"
                                value={additionalVisit.visit_date}
                                onChange={(e) => setAdditionalVisit({...additionalVisit, visit_date: e.target.value})}
                                className="h-9"
                              />
                            </div>
                            <div>
                              <Label className="text-xs">Visit Type</Label>
                              <Select
                                value={additionalVisit.visit_type}
                                onValueChange={(v) => setAdditionalVisit({...additionalVisit, visit_type: v})}
                              >
                                <SelectTrigger className="h-9">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="Phone Call">Phone Call</SelectItem>
                                  <SelectItem value="Home Visit">Home Visit</SelectItem>
                                  <SelectItem value="Hospital Visit">Hospital Visit</SelectItem>
                                  <SelectItem value="Office Visit">Office Visit</SelectItem>
                                  <SelectItem value="Emergency Visit">Emergency Visit</SelectItem>
                                  <SelectItem value="Other">Other</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="text-xs">Notes</Label>
                              <Textarea
                                placeholder="What happened during this visit..."
                                value={additionalVisit.notes}
                                onChange={(e) => setAdditionalVisit({...additionalVisit, notes: e.target.value})}
                                rows={2}
                                className="text-sm"
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" variant="outline" onClick={() => toggleAdditionalForm(event.id)}>
                                Cancel
                              </Button>
                              <Button size="sm" onClick={() => logAdditionalVisit(event)} className="bg-teal-500 hover:bg-teal-600">
                                Log Visit
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>

                    </div>
                  </div>
                ))
          )}
        </TabsContent>
        
        {/* Accident/Illness Tab */}
        <TabsContent value="accident">
          {careEvents.filter(e => e.event_type === 'accident_illness' && !e.accident_stage_id && !e.care_event_id).length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No accident/illness visits recorded.</p>
          ) : (
            careEvents.filter(e => e.event_type === 'accident_illness' && !e.accident_stage_id && !e.care_event_id).map(event => (
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
                          const isCompleted = stage.completed === true;
                          return (
                          <div key={stage.id} className={`flex items-center gap-3 p-2 bg-blue-50 rounded ${isIgnored ? 'opacity-60' : ''}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                              isCompleted ? 'bg-blue-500' : 'bg-blue-200'
                            }`}>
                              {isCompleted ? (
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
                            
                            {/* Show button for all states */}
                            <div className="flex gap-1">
                              {isCompleted && (
                                <Button size="sm" variant="outline" className="min-h-[44px] bg-green-50 text-green-700 border-green-200" disabled>
                                  Completed
                                </Button>
                              )}
                              {isIgnored && (
                                <Button size="sm" variant="outline" className="min-h-[44px] bg-gray-100 text-gray-500 border-gray-300" disabled>
                                  Ignored
                                </Button>
                              )}
                              {!isCompleted && !isIgnored && (
                                <Button size="sm" variant="outline" className="min-h-[44px]" onClick={async () => {
                                  try {
                                    await api.post(`/accident-followup/${stage.id}/complete`);
                                    toast.success('Follow-up completed');
                                    queryClient.invalidateQueries(['member', id]);
                                  } catch (error) {
                                    toast.error(t('toasts.failed'));
                                  }
                                }}>
                                  Mark Complete
                                </Button>
                              )}
                              
                              {/* Three dots menu */}
                              {(isCompleted || isIgnored) && (
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button size="sm" variant="ghost">
                                      <MoreVertical className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={async () => {
                                      try {
                                        await api.post(`/accident-followup/${stage.id}/undo`);
                                        toast.success(t('toasts.action_undone'));
                                        queryClient.invalidateQueries(['member', id]);
                                      } catch (error) {
                                        toast.error(t('toasts.failed_undo'));
                                      }
                                    }}>
                                      Undo
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              )}
                              
                              {!isCompleted && !isIgnored && (
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button size="sm" variant="ghost">
                                      <MoreVertical className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={async () => {
                                      try {
                                        await api.post(`/accident-followup/${stage.id}/ignore`);
                                        toast.success('Follow-up ignored');
                                        queryClient.invalidateQueries(['member', id]);
                                      } catch (error) {
                                        toast.error('Failed to ignore');
                                        console.error('Error ignoring accident stage:', error);
                                      }
                                    }}>
                                      Ignore
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              )}
                            </div>
                          </div>
                          );
                        })}
                      </div>
                      
                      {/* Display additional visits for accident - Simplified */}
                      <div className="mt-4">
                        <h5 className="text-sm font-semibold mb-3 text-gray-700">📝 Additional Visits:</h5>
                        {careEvents
                          .filter(e => e.care_event_id === event.id && e.followup_type === "additional")
                          .map((visit) => (
                            <div key={visit.id} className="flex items-start gap-3 p-2 bg-gray-50 rounded border border-gray-200 mb-2">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center bg-gray-300">
                                <span className="text-white text-xs">✓</span>
                              </div>
                              <div className="flex-1">
                                <p className="text-sm font-medium text-gray-800">
                                  {visit.title}
                                </p>
                                <p className="text-xs text-gray-600">
                                  {formatDate(visit.event_date, 'dd MMM yyyy')}
                                </p>
                                {visit.description && (
                                  <p className="text-xs text-gray-600 mt-1">{visit.description}</p>
                                )}
                                {visit.created_by_user_name && (
                                  <p className="text-xs text-gray-500 mt-1">
                                    By: {visit.created_by_user_name}
                                  </p>
                                )}
                              </div>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-red-500 hover:text-red-700"
                                onClick={() => {
                                  showConfirm(
                                    'Delete Additional Visit',
                                    'Are you sure you want to delete this additional visit? This action cannot be undone.',
                                    async () => {
                                      try {
                                        await api.delete(`/care-events/${visit.id}`);
                                        toast.success('Visit deleted');
                                        queryClient.invalidateQueries(['member', id]);
                                        closeConfirm();
                                      } catch (error) {
                                        toast.error('Failed to delete');
                                        closeConfirm();
                                      }
                                    }
                                  );
                                }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          ))}
                        {careEvents.filter(e => e.care_event_id === event.id && e.followup_type === "additional").length === 0 && (
                          <p className="text-xs text-gray-500 italic mb-3">No additional visits yet</p>
                        )}
                        
                        {/* Inline form to log additional visit for accident - now at bottom */}
                        {!additionalVisitForm[event.id] ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-full gap-2 border-dashed"
                            onClick={() => toggleAdditionalForm(event.id)}
                          >
                            <Plus className="w-4 h-4" />
                            Log Additional Visit
                          </Button>
                        ) : (
                          <div className="space-y-3 p-3 bg-white rounded border border-blue-300">
                            <h6 className="font-medium text-sm">Log Additional Visit</h6>
                            <div>
                              <Label className="text-xs">Visit Date</Label>
                              <Input
                                type="date"
                                value={additionalVisit.visit_date}
                                onChange={(e) => setAdditionalVisit({...additionalVisit, visit_date: e.target.value})}
                                className="h-9"
                              />
                            </div>
                            <div>
                              <Label className="text-xs">Visit Type</Label>
                              <Select
                                value={additionalVisit.visit_type}
                                onValueChange={(v) => setAdditionalVisit({...additionalVisit, visit_type: v})}
                              >
                                <SelectTrigger className="h-9">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="Phone Call">Phone Call</SelectItem>
                                  <SelectItem value="Home Visit">Home Visit</SelectItem>
                                  <SelectItem value="Hospital Visit">Hospital Visit</SelectItem>
                                  <SelectItem value="Office Visit">Office Visit</SelectItem>
                                  <SelectItem value="Emergency Visit">Emergency Visit</SelectItem>
                                  <SelectItem value="Other">Other</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="text-xs">Notes</Label>
                              <Textarea
                                placeholder="What happened during this visit..."
                                value={additionalVisit.notes}
                                onChange={(e) => setAdditionalVisit({...additionalVisit, notes: e.target.value})}
                                rows={2}
                                className="text-sm"
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" variant="outline" onClick={() => toggleAdditionalForm(event.id)}>
                                Cancel
                              </Button>
                              <Button size="sm" onClick={() => logAdditionalVisit(event)} className="bg-teal-500 hover:bg-teal-600">
                                Log Visit
                              </Button>
                            </div>
                          </div>
                        )}
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
                                  showConfirm(
                                    'Mark Payment as Distributed',
                                    'Mark this scheduled payment as distributed? This will advance the schedule to the next occurrence.',
                                    async () => {
                                      try {
                                        await api.post(`/financial-aid-schedules/${schedule.id}/mark-distributed`);
                                        toast.success('Payment distributed! Schedule advanced to next occurrence.');
                                        queryClient.invalidateQueries(['member', id]);
                                        queryClient.invalidateQueries(['dashboard']);
                                        closeConfirm();
                                      } catch (error) {
                                        toast.error('Failed to mark payment');
                                        closeConfirm();
                                      }
                                    }
                                  );
                                }} className="text-green-600">
                                  <Check className="w-4 h-4 mr-2" />
                                  Distributed
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={async () => {
                                  showConfirm(
                                    'Stop Aid Schedule',
                                    'Stop this aid schedule? Ignored history will be preserved. You can re-enable it later.',
                                    async () => {
                                      try {
                                        await api.post(`/financial-aid-schedules/${schedule.id}/stop`);
                                        toast.success('Schedule stopped');
                                        queryClient.invalidateQueries(['member', id]);
                                        queryClient.invalidateQueries(['dashboard']);
                                        closeConfirm();
                                      } catch (error) {
                                        toast.error('Failed to stop schedule');
                                        closeConfirm();
                                      }
                                    }
                                  );
                                }} className="text-red-600">
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  Stop Schedule
                                </DropdownMenuItem>
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      const response = await api.post(`/financial-aid-schedules/${schedule.id}/ignore`);
                                      toast.success(`Payment ignored! Next payment: ${response.data.next_occurrence}`);
                                      queryClient.invalidateQueries(['member', id]);
                                      queryClient.invalidateQueries(['dashboard']);
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
                                        showConfirm(
                                          'Remove Ignored Occurrence',
                                          `Remove this ignored occurrence (${formatDate(date, 'dd MMM yyyy')})? This payment will be marked as due again.`,
                                          async () => {
                                            try {
                                              await api.delete(`/financial-aid-schedules/${schedule.id}/ignored-occurrence/${date}`);
                                              toast.success('Ignored occurrence removed');
                                              queryClient.invalidateQueries(['member', id]);
                                              closeConfirm();
                                            } catch (error) {
                                              toast.error('Failed to remove');
                                              closeConfirm();
                                            }
                                          }
                                        );
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
                                  showConfirm(
                                    'Clear All Ignored Payments',
                                    'Clear all ignored payments for this schedule? Future payments will continue as scheduled.',
                                    async () => {
                                      try {
                                        // Use new endpoint to clear ignored occurrences
                                        await api.post(`/financial-aid-schedules/${schedule.id}/clear-ignored`);
                                        toast.success('All ignored payments cleared');
                                        queryClient.invalidateQueries(['member', id]);
                                        queryClient.invalidateQueries(['dashboard']);
                                        closeConfirm();
                                      } catch (error) {
                                        toast.error(t('toasts.failed_delete'));
                                        closeConfirm();
                                      }
                                    }
                                  );
                                }} className="text-red-600">
                                  <Trash2 className="w-4 h-4 mr-2" />Clear All Ignored Payments
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

      {/* Confirmation Dialog */}
      <ConfirmDialog
        open={confirmDialog.open}
        onOpenChange={(open) => !open && closeConfirm()}
        title={confirmDialog.title}
        description={confirmDialog.description}
        onConfirm={confirmDialog.onConfirm}
        onCancel={closeConfirm}
      />
    </div>
  );
};

export default MemberDetail;