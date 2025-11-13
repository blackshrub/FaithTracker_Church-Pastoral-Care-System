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
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { ArrowLeft, Plus, Send, CheckCircle2, Calendar, Heart, Hospital, DollarSign, MoreVertical, Edit, Trash2 } from 'lucide-react';
import { MemberAvatar } from '@/components/MemberAvatar';
import { EngagementBadge } from '@/components/EngagementBadge';
import { EventTypeBadge } from '@/components/EventTypeBadge';
import { format } from 'date-fns';

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
    month_of_year: 1
  });
  
  useEffect(() => {
    if (id) {
      loadMemberData();
    }
  }, [id]);
  
  const loadMemberData = async () => {
    try {
      setLoading(true);
      const [memberRes, eventsRes, griefRes, accidentRes, aidSchedulesRes] = await Promise.all([
        axios.get(`${API}/members/${id}`),
        axios.get(`${API}/care-events?member_id=${id}`),
        axios.get(`${API}/grief-support/member/${id}`),
        axios.get(`${API}/accident-followup/member/${id}`),
        axios.get(`${API}/financial-aid-schedules/member/${id}`)
      ]);
      
      setMember(memberRes.data);
      setCareEvents(eventsRes.data);
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
          toast.success('Financial aid recorded as given!');
        } else {
          // Scheduled aid: Create schedule (future payments)
          const scheduleData = {
            member_id: id,
            campus_id: member.campus_id,
            title: newEvent.title,
            aid_type: newEvent.aid_type,
            aid_amount: parseFloat(newEvent.aid_amount),
            frequency: newEvent.schedule_frequency,
            start_date: newEvent.schedule_start_date,
            end_date: newEvent.schedule_end_date || null,
            day_of_week: newEvent.day_of_week,
            day_of_month: newEvent.day_of_month,
            month_of_year: newEvent.month_of_year,
            notes: newEvent.description
          };
          await axios.post(`${API}/financial-aid-schedules`, scheduleData);
          toast.success('Financial aid schedule created!');
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
        month_of_year: 1
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
      toast.success('Event deleted');
      loadMemberData();
    } catch (error) {
      toast.error('Failed to delete');
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/members">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Members
          </Button>
        </Link>
        
        <div className="flex items-start gap-6">
          <MemberAvatar member={member} size="xl" />
          <div className="flex-1">
            <h1 className="text-3xl font-manrope font-bold text-foreground">{member.name}</h1>
            <p className="text-muted-foreground mt-1">{member.phone}</p>
            <div className="flex items-center gap-4 mt-3">
              <EngagementBadge status={member.engagement_status} days={member.days_since_last_contact} />
              {member.last_contact_date && (
                <span className="text-sm text-muted-foreground">
                  {t('last_contact')}: {formatDate(member.last_contact_date, 'dd MMM yyyy')}
                </span>
              )}
            </div>
          </div>
          
          <Dialog open={eventModalOpen} onOpenChange={setEventModalOpen}>
            <DialogTrigger asChild>
              <Button className="bg-teal-500 hover:bg-teal-600 text-white" data-testid="add-care-event-button">
                <Plus className="w-4 h-4 mr-2" />
                {t('add_care_event')}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="add-care-event-modal">
              <DialogHeader>
                <DialogTitle>{t('add_care_event')}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleAddCareEvent} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Event Type *</Label>
                    <Select value={newEvent.event_type} onValueChange={(v) => setNewEvent({...newEvent, event_type: v})} required>
                      <SelectTrigger data-testid="event-type-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="birthday">🎂 {t('event_types.birthday')}</SelectItem>
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
                    <div className="space-y-2">
                      <Label>Event Date *</Label>
                      <Input
                        type="date"
                        value={newEvent.event_date}
                        onChange={(e) => setNewEvent({...newEvent, event_date: e.target.value})}
                        required
                        data-testid="event-date-input"
                      />
                    </div>
                  )}
                </div>
                
                <div className="space-y-2">
                  <Label>Title *</Label>
                  <Input
                    value={newEvent.title}
                    onChange={(e) => setNewEvent({...newEvent, title: e.target.value})}
                    placeholder="e.g., Birthday Celebration"
                    required
                    data-testid="event-title-input"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Textarea
                    value={newEvent.description}
                    onChange={(e) => setNewEvent({...newEvent, description: e.target.value})}
                    rows={3}
                    data-testid="event-description-input"
                  />
                </div>
                
                {/* Conditional Fields */}
                {newEvent.event_type === 'grief_loss' && (
                  <div className="space-y-4 p-4 bg-purple-50 dark:bg-purple-950 rounded-lg border border-purple-200">
                    <p className="text-sm font-medium text-purple-900 dark:text-purple-100">
                      ⭐ {t('success_messages.grief_timeline_generated')}
                    </p>
                    <div className="space-y-2">
                      <Label>Relationship to Deceased *</Label>
                      <Select value={newEvent.grief_relationship} onValueChange={(v) => setNewEvent({...newEvent, grief_relationship: v})} required>
                        <SelectTrigger>
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
                    <div className="space-y-2">
                      <Label>Hospital/Medical Facility Name</Label>
                      <Input
                        value={newEvent.hospital_name}
                        onChange={(e) => setNewEvent({...newEvent, hospital_name: e.target.value})}
                        placeholder="RSU Jakarta"
                      />
                    </div>
                  </div>
                )}
                
                {newEvent.event_type === 'financial_aid' && (
                  <div className="space-y-4 p-4 bg-green-50 dark:bg-green-950 rounded-lg border border-green-200">
                    <h4 className="font-semibold text-green-900 dark:text-green-100">Financial Aid Details</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Aid Type *</Label>
                        <Select value={newEvent.aid_type} onValueChange={(v) => setNewEvent({...newEvent, aid_type: v})} required>
                          <SelectTrigger><SelectValue /></SelectTrigger>
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
                        <Label>Amount (Rp) *</Label>
                        <Input
                          type="number"
                          value={newEvent.aid_amount}
                          onChange={(e) => setNewEvent({...newEvent, aid_amount: e.target.value})}
                          placeholder="1500000"
                          required
                        />
                      </div>
                    </div>
                    
                    {/* Financial Aid Scheduling */}
                    <div className="space-y-4 border-t pt-4">
                      <h5 className="font-semibold text-green-800 dark:text-green-200">📅 Payment Type</h5>
                      <div>
                        <Label>Frequency *</Label>
                        <Select value={newEvent.schedule_frequency} onValueChange={(v) => setNewEvent({...newEvent, schedule_frequency: v})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
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
                          <Label>Payment Date *</Label>
                          <Input
                            type="date"
                            value={newEvent.payment_date}
                            onChange={(e) => setNewEvent({...newEvent, payment_date: e.target.value})}
                            required
                          />
                          <p className="text-xs text-muted-foreground mt-1">Date when aid was given</p>
                        </div>
                      )}
                      
                      {newEvent.schedule_frequency === 'weekly' && (
                        <div className="grid grid-cols-3 gap-3 p-3 bg-blue-50 dark:bg-blue-950 rounded">
                          <div>
                            <Label className="text-xs">Start Date *</Label>
                            <Input
                              type="date"
                              value={newEvent.schedule_start_date}
                              onChange={(e) => setNewEvent({...newEvent, schedule_start_date: e.target.value})}
                              required
                            />
                          </div>
                          <div>
                            <Label className="text-xs">Day of Week *</Label>
                            <Select value={newEvent.day_of_week} onValueChange={(v) => setNewEvent({...newEvent, day_of_week: v})}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
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
                            <Label className="text-xs">End Date (optional)</Label>
                            <Input
                              type="date"
                              value={newEvent.schedule_end_date}
                              onChange={(e) => setNewEvent({...newEvent, schedule_end_date: e.target.value})}
                            />
                          </div>
                        </div>
                      )}
                      
                      {newEvent.schedule_frequency === 'monthly' && (
                        <div className="grid grid-cols-3 gap-3 p-3 bg-purple-50 dark:bg-purple-950 rounded">
                          <div>
                            <Label className="text-xs">Start Month/Year *</Label>
                            <Input
                              type="month"
                              value={newEvent.schedule_start_date.substring(0, 7)}
                              onChange={(e) => setNewEvent({...newEvent, schedule_start_date: e.target.value + '-01'})}
                              required
                            />
                          </div>
                          <div>
                            <Label className="text-xs">Day of Month *</Label>
                            <Input
                              type="number"
                              min="1"
                              max="31"
                              value={newEvent.day_of_month}
                              onChange={(e) => setNewEvent({...newEvent, day_of_month: parseInt(e.target.value) || 1})}
                              required
                            />
                          </div>
                          <div>
                            <Label className="text-xs">End Month/Year (optional)</Label>
                            <Input
                              type="month"
                              value={newEvent.schedule_end_date ? newEvent.schedule_end_date.substring(0, 7) : ''}
                              onChange={(e) => setNewEvent({...newEvent, schedule_end_date: e.target.value ? e.target.value + '-01' : ''})}
                            />
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
                
                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="outline" onClick={() => setEventModalOpen(false)}>
                    {t('cancel')}
                  </Button>
                  <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white" data-testid="save-care-event-button">
                    {t('save')}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>
      
      {/* Member Info Card */}
      <Card className="border-border">
        <CardContent className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
        <div className="overflow-x-auto">
          <TabsList className="inline-flex w-auto min-w-full">
            <TabsTrigger value="timeline" data-testid="tab-timeline">
              <Calendar className="w-4 h-4 mr-2" />Timeline
            </TabsTrigger>
            {griefTimeline.length > 0 && (
              <TabsTrigger value="grief" data-testid="tab-grief">
                <Heart className="w-4 h-4 mr-2" />Grief ({griefTimeline.length})
              </TabsTrigger>
            )}
            {careEvents.filter(e => e.event_type === 'accident_illness').length > 0 && (
              <TabsTrigger value="accident" data-testid="tab-accident">
                <Hospital className="w-4 h-4 mr-2" />Accident/Illness ({careEvents.filter(e => e.event_type === 'accident_illness').length})
              </TabsTrigger>
            )}
            {careEvents.filter(e => e.event_type === 'financial_aid').length > 0 && (
              <TabsTrigger value="aid" data-testid="tab-aid">
                <DollarSign className="w-4 h-4 mr-2" />Aid ({careEvents.filter(e => e.event_type === 'financial_aid').length})
              </TabsTrigger>
            )}
          </TabsList>
        </div>
        
        {/* Timeline Tab */}
        <TabsContent value="timeline" className="space-y-4">
          <Card>
            <CardContent className="p-6">
              {careEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  {t('empty_states.no_care_events')}
                </p>
              ) : (
                <div className="space-y-4">
                  {careEvents.map((event) => (
                    <div key={event.id} className="flex gap-4 pb-4 border-l-2 border-primary-200 pl-6 ml-3 relative timeline-item" data-testid={`care-event-${event.id}`}>
                      <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-primary-500 border-2 border-background"></div>
                      <div className="flex-1">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <EventTypeBadge type={event.event_type} />
                              <span className="text-xs text-muted-foreground">
                                {formatDate(event.event_date, 'dd MMM yyyy')}
                              </span>
                              {event.completed && (
                                <CheckCircle2 className="w-4 h-4 text-green-600" />
                              )}
                            </div>
                            <h5 className="font-playfair font-semibold text-sm text-foreground mb-1">{event.title}</h5>
                            {event.description && (
                              <p className="text-sm text-muted-foreground">{event.description}</p>
                            )}
                            {event.aid_amount && (
                              <p className="text-sm text-green-700 font-medium mt-1">
                                Rp {event.aid_amount.toLocaleString('id-ID')}
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
                                <Trash2 className="w-4 h-4 mr-2" />Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Grief Support Tab */}
        <TabsContent value="grief" className="space-y-4">
          <Card>
            <CardContent className="p-6">
              {griefTimeline.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No active grief support timeline.
                </p>
              ) : (
                <div className="space-y-6">
                  {griefTimeline.map((stage, index) => (
                    <div key={stage.id} className="relative" data-testid={`grief-stage-${stage.id}`}>
                      {index > 0 && <div className="absolute left-6 top-0 w-0.5 h-6 bg-primary-200 -mt-6"></div>}
                      <div className="flex gap-4">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                          stage.completed ? 'bg-green-500' : 'bg-primary-100'
                        }`}>
                          {stage.completed ? (
                            <CheckCircle2 className="w-6 h-6 text-white" />
                          ) : (
                            <span className="text-sm font-bold text-primary-700">{index + 1}</span>
                          )}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-manrope font-semibold text-foreground">
                            {t(`grief_stages.${stage.stage}`)}
                          </h4>
                          <p className="text-sm text-muted-foreground">
                            {formatDate(stage.scheduled_date, 'dd MMM yyyy')}
                          </p>
                          {stage.notes && (
                            <p className="text-sm text-muted-foreground mt-2 italic">
                              Notes: {stage.notes}
                            </p>
                          )}
                          {!stage.completed && (
                            <div className="flex gap-2 mt-3">
                              <Button
                                size="sm"
                                onClick={() => completeGriefStage(stage.id)}
                                data-testid={`complete-grief-stage-${stage.id}`}
                              >
                                {t('mark_complete')}
                              </Button>
                            </div>
                          )}
                          {stage.completed && (
                            <p className="text-xs text-green-600 mt-2">
                              Completed: {formatDate(stage.completed_at, 'dd MMM yyyy')}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Accident/Illness Tab */}
        <TabsContent value="accident">
          <Card>
            <CardContent className="p-6">
              {careEvents.filter(e => e.event_type === 'accident_illness').length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No accident/illness visits recorded.</p>
              ) : (
                careEvents.filter(e => e.event_type === 'accident_illness').map(event => (
                  <div key={event.id} className="space-y-4 mb-6 p-4 border rounded-lg">
                    <div>
                      <h4 className="font-semibold">{event.title}</h4>
                      <p className="text-sm text-muted-foreground">
                        Date: {formatDate(event.event_date, 'dd MMM yyyy')}
                      </p>
                      {event.hospital_name && (
                        <p className="text-sm text-muted-foreground">
                          Facility: {event.hospital_name}
                        </p>
                      )}
                    </div>
                    
                    {/* Follow-up Timeline within each accident record */}
                    <div className="mt-4">
                      <h5 className="text-sm font-semibold mb-3">Follow-up Schedule:</h5>
                      <div className="space-y-3">
                        {accidentTimeline.filter(t => t.care_event_id === event.id).map((stage, index) => (
                          <div key={stage.id} className="flex items-center gap-3 p-2 bg-blue-50 rounded">
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
                            {!stage.completed && (
                              <Button size="sm" variant="outline" onClick={async () => {
                                try {
                                  await axios.post(`${API}/accident-followup/${stage.id}/complete`);
                                  toast.success('Follow-up completed');
                                  loadMemberData();
                                } catch (error) {
                                  toast.error('Failed');
                                }
                              }}>
                                Complete
                              </Button>
                            )}
                          </div>
                        ))}
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
            </CardContent>
          </Card>
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
                      <div key={event.id} className="p-4 bg-green-50 rounded-lg border border-green-200">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-semibold text-foreground">{t(`aid_types.${event.aid_type}`)}</p>
                            <p className="text-sm text-muted-foreground">
                              {formatDate(event.event_date, 'dd MMM yyyy')}
                            </p>
                            {event.aid_notes && (
                              <p className="text-sm text-muted-foreground mt-1">{event.aid_notes}</p>
                            )}
                          </div>
                          <p className="text-lg font-bold text-green-700">
                            Rp {event.aid_amount?.toLocaleString('id-ID')}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Scheduled Financial Aid (Future payments) */}
                <div className="border-t pt-4">
                  <h4 className="font-semibold text-foreground">Upcoming Scheduled Payments</h4>
                  {aidSchedules.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4">No scheduled aid.</p>
                  ) : (
                    <div className="space-y-3 mt-3">
                      {aidSchedules.slice(0, 5).map(schedule => (
                        <div key={schedule.id} className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <p className="font-semibold text-foreground">{schedule.title}</p>
                              <p className="text-sm text-muted-foreground">
                                {schedule.frequency} - Next: {formatDate(schedule.next_occurrence, 'dd MMM yyyy')}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {schedule.aid_type} - Rp {schedule.aid_amount?.toLocaleString('id-ID')}
                              </p>
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" variant="outline" onClick={async () => {
                                if (window.confirm('Mark this scheduled payment as distributed?')) {
                                  try {
                                    // Create care event for this payment
                                    await axios.post(`${API}/care-events`, {
                                      member_id: id,
                                      campus_id: member.campus_id,
                                      event_type: 'financial_aid',
                                      event_date: schedule.next_occurrence,
                                      title: schedule.title,
                                      aid_type: schedule.aid_type,
                                      aid_amount: schedule.aid_amount,
                                      aid_notes: `From schedule: ${schedule.frequency}`
                                    });
                                    toast.success('Payment marked as distributed!');
                                    loadMemberData();
                                  } catch (error) {
                                    toast.error('Failed to mark payment');
                                  }
                                }
                              }}>
                                Mark Distributed
                              </Button>
                              <Button size="sm" variant="ghost" className="text-red-600" onClick={async () => {
                                if (window.confirm('Stop this aid schedule?')) {
                                  try {
                                    await axios.post(`${API}/financial-aid-schedules/${schedule.id}/stop`);
                                    toast.success('Schedule stopped');
                                    loadMemberData();
                                  } catch (error) {
                                    toast.error('Failed to stop schedule');
                                  }
                                }
                              }}>
                                Stop Schedule
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* Total Summary */}
                <div className="pt-4 border-t">
                  <p className="text-right font-semibold text-foreground">
                    Total Given: Rp {careEvents.filter(e => e.event_type === 'financial_aid').reduce((sum, e) => sum + (e.aid_amount || 0), 0).toLocaleString('id-ID')}
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