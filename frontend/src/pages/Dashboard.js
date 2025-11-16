import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import LazyImage from '@/components/LazyImage';
import { MemberAvatar } from '@/components/MemberAvatar';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Heart, Users, Hospital, Calendar, AlertTriangle, DollarSign, Bell, Plus, Check, MoreVertical, MessageSquare } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatDate = (dateStr, format = 'short') => {
  try {
    if (format === 'dd MMM yyyy') {
      return new Date(dateStr).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
    }
    return new Date(dateStr).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
  } catch { return dateStr; }
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

const markBirthdayComplete = async (eventId, setBirthdaysToday) => {
  try {
    await axios.post(`${API}/care-events/${eventId}/complete`);
    toast.success('Birthday task completed!');
    // Update local state
    setBirthdaysToday(prev => prev.filter(b => b.id !== eventId));
  } catch (error) {
    toast.error('Failed to complete');
  }
};

const markGriefStageComplete = async (stageId, setGriefDue) => {
  try {
    await axios.post(`${API}/grief-support/${stageId}/complete`);
    toast.success('Grief stage completed!');
    // Update local state
    setGriefDue(prev => prev.filter(s => s.id !== stageId));
  } catch (error) {
    toast.error('Failed to complete');
  }
};

const markAccidentComplete = async (eventId, setAccidentFollowUp) => {
  try {
    await axios.post(`${API}/care-events/${eventId}/complete`);
    toast.success('Accident follow-up completed!');
    // Update local state
    setAccidentFollowUp(prev => prev.filter(a => a.id !== eventId));
  } catch (error) {
    toast.error('Failed to complete');
  }
};

const markMemberContacted = async (memberId, memberName, user, setAtRiskMembers, setDisconnectedMembers) => {
  try {
    // Create a regular contact event which updates last_contact_date
    await axios.post(`${API}/care-events`, {
      member_id: memberId,
      campus_id: user?.campus_id || '2b3f9094-eef4-4af4-a3ff-730ef4adeb8a',
      event_type: 'regular_contact',
      event_date: new Date().toISOString().split('T')[0],
      title: `Contact with ${memberName}`,
      description: 'Contacted via Reminders page'
    });
    toast.success(`${memberName} marked as contacted! Status updated to Active.`);
    // Update local state - remove from both at-risk and disconnected
    setAtRiskMembers(prev => prev.filter(m => m.id !== memberId));
    setDisconnectedMembers(prev => prev.filter(m => m.id !== memberId));
  } catch (error) {
    toast.error('Failed to mark as contacted');
    console.error('Error marking member contacted:', error);
  }
};

export const Dashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [birthdaysToday, setBirthdaysToday] = useState([]);
  const [overdueBirthdays, setOverdueBirthdays] = useState([]);
  const [todayTasks, setTodayTasks] = useState([]);
  const [griefDue, setGriefDue] = useState([]);
  const [griefToday, setGriefToday] = useState([]);
  const [hospitalFollowUp, setHospitalFollowUp] = useState([]);
  const [accidentFollowUp, setAccidentFollowUp] = useState([]);
  const [atRiskMembers, setAtRiskMembers] = useState([]);
  const [disconnectedMembers, setDisconnectedMembers] = useState([]);
  const [upcomingBirthdays, setUpcomingBirthdays] = useState([]);
  const [upcomingTasks, setUpcomingTasks] = useState([]);
  const [financialAidDue, setFinancialAidDue] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [quickEventOpen, setQuickEventOpen] = useState(false);
  const [allMembers, setAllMembers] = useState([]);
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
    loadReminders();
  }, []);
  
  const loadReminders = async () => {
    try {
      setLoading(true);
      
      // Use optimized pre-calculated endpoint
      const response = await axios.get(`${API}/dashboard/reminders`);
      const data = response.data;
      
      // Set all state from pre-calculated data
      setBirthdaysToday(data.birthdays_today || []);
      setOverdueBirthdays(data.overdue_birthdays || []);
      setTodayTasks(data.today_tasks || []);
      setUpcomingBirthdays(data.upcoming_birthdays || []);
      setUpcomingTasks(data.upcoming_tasks || []);
      setGriefToday(data.grief_today || []);
      setGriefDue(data.grief_today || []); // Same as grief_today
      setAccidentFollowUp(data.accident_followup || []);
      setHospitalFollowUp([]);
      setAtRiskMembers(data.at_risk_members || []);
      setDisconnectedMembers(data.disconnected_members || []);
      setFinancialAidDue(data.financial_aid_due || []);
      setSuggestions(data.ai_suggestions || []);
      
      // Also load all members for the quick event form (in background, non-blocking)
      loadAllMembersForForm();
      
    } catch (error) {
      console.error('Error loading reminders:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };
  
  const loadAllMembersForForm = async () => {
    try {
      const membersRes = await axios.get(`${API}/members?limit=1000`);
      setAllMembers(membersRes.data);
    } catch (error) {
      console.error('Error loading members for form:', error);
    }
  };
  

  
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
            await axios.post(`${API}/financial-aid-schedules`, {
              member_id: memberId,
              campus_id: member.campus_id,
              title: autoTitle,
              aid_type: quickEvent.aid_type,
              aid_amount: parseFloat(quickEvent.aid_amount),
              frequency: quickEvent.schedule_frequency,
              start_date: quickEvent.schedule_frequency === 'weekly' 
                ? new Date().toISOString().split('T')[0]  // Use today for weekly
                : quickEvent.schedule_start_date,
              end_date: quickEvent.schedule_end_date || null,
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
      // Refresh dashboard to show new tasks
      loadReminders();
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

  
  if (loading) return <div>{t('loading')}</div>;
  
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 max-w-full">
        <Card className="card-border-left-teal shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-muted-foreground mb-1">{t('total_members')}</p>
                <p className="text-4xl font-playfair font-bold">805</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
                <Users className="w-7 h-7 text-teal-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-amber shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-muted-foreground mb-1">{t('total_interactions')}</p>
                <p className="text-4xl font-playfair font-bold">{birthdaysToday.length + griefToday.length + hospitalFollowUp.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                <Calendar className="w-7 h-7 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-pink shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-muted-foreground mb-1">{t('pending_reminders')}</p>
                <p className="text-4xl font-playfair font-bold">{griefDue.length + financialAidDue.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-pink-100 flex items-center justify-center flex-shrink-0">
                <Bell className="w-7 h-7 text-pink-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-purple shadow-sm hover:shadow-md transition-all min-w-0">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-muted-foreground mb-1">{t('at_risk_disconnected')}</p>
                <p className="text-4xl font-playfair font-bold">{atRiskMembers.length + disconnectedMembers.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                <Heart className="w-7 h-7 text-purple-600" />
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
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{t('quick_care_event_multi')}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleQuickEvent} className="space-y-6">
                {/* Member Selection */}
                <div className="space-y-3">
                  <Label>{t('select_members_required')}</Label>
                  <Input
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder={t('type_member_name_search')}
                  />
                  
                  {selectedMemberIds.length > 0 && (
                    <div className="p-3 bg-teal-50 rounded border">
                      <p className="font-semibold text-sm mb-2">Selected Members ({selectedMemberIds.length}):</p>
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
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t('event_type_required')}</Label>
                    <Select value={quickEvent.event_type} onValueChange={(v) => setQuickEvent({...quickEvent, event_type: v})}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
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
                  {quickEvent.event_type !== 'financial_aid' && (
                    <div>
                      <Label>{t('event_date_required')}</Label>
                      <Input type="date" value={quickEvent.event_date} onChange={(e) => setQuickEvent({...quickEvent, event_date: e.target.value})} required />
                    </div>
                  )}
                </div>
                
                <div>
                  <Label>Description</Label>
                  <Input value={quickEvent.description} onChange={(e) => setQuickEvent({...quickEvent, description: e.target.value})} placeholder={t('additional_details')} />
                </div>
                
                {/* Title only for Financial Aid */}
                {quickEvent.event_type === 'financial_aid' && (
                  <div>
                    <Label>Aid Name/Title *</Label>
                    <Input value={quickEvent.title} onChange={(e) => setQuickEvent({...quickEvent, title: e.target.value})} placeholder="e.g., Monthly Education Support" required />
                  </div>
                )}
                
                {/* Conditional Fields */}
                {quickEvent.event_type === 'grief_loss' && (
                  <div className="space-y-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
                    <p className="text-sm font-medium text-purple-900">⭐ Auto-generates 6-stage grief timeline</p>
                    <div>
                      <Label>Relationship to Deceased *</Label>
                      <Select value={quickEvent.grief_relationship} onValueChange={(v) => setQuickEvent({...quickEvent, grief_relationship: v})} required>
                        <SelectTrigger><SelectValue placeholder="Select relationship" /></SelectTrigger>
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
                      <Label>Hospital/Medical Facility Name</Label>
                      <Input
                        value={quickEvent.hospital_name}
                        onChange={(e) => setQuickEvent({...quickEvent, hospital_name: e.target.value})}
                        placeholder="RSU Jakarta"
                      />
                    </div>
                  </div>
                )}
                
                {quickEvent.event_type === 'financial_aid' && (
                  <div className="space-y-4 p-4 bg-green-50 rounded-lg border border-green-200">
                    <h4 className="font-semibold text-green-900">Financial Aid Details</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Aid Type *</Label>
                        <Select value={quickEvent.aid_type} onValueChange={(v) => setQuickEvent({...quickEvent, aid_type: v})} required>
                          <SelectTrigger><SelectValue /></SelectTrigger>
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
                        <Label>Amount (Rp) *</Label>
                        <Input
                          type="number"
                          value={quickEvent.aid_amount}
                          onChange={(e) => setQuickEvent({...quickEvent, aid_amount: e.target.value})}
                          placeholder="1500000"
                          required
                        />
                      </div>
                    </div>
                    
                    {/* Financial Aid Scheduling */}
                    <div className="space-y-4 border-t pt-4">
                      <h5 className="font-semibold text-green-800">📅 Payment Type</h5>
                      <div>
                        <Label>Frequency *</Label>
                        <Select value={quickEvent.schedule_frequency || 'one_time'} onValueChange={(v) => setQuickEvent({...quickEvent, schedule_frequency: v})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
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
                          <Label>Payment Date *</Label>
                          <Input
                            type="date"
                            value={quickEvent.payment_date || quickEvent.event_date}
                            onChange={(e) => setQuickEvent({...quickEvent, payment_date: e.target.value})}
                            required
                          />
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'weekly' && (
                        <div className="grid grid-cols-2 gap-3 p-3 bg-blue-50 rounded">
                          <div>
                            <Label className="text-xs">Day of Week *</Label>
                            <Select value={quickEvent.day_of_week || 'monday'} onValueChange={(v) => setQuickEvent({...quickEvent, day_of_week: v})}>
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
                            <Input type="date" value={quickEvent.schedule_end_date || ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value})} />
                          </div>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'monthly' && (
                        <div className="grid grid-cols-3 gap-3 p-3 bg-purple-50 rounded">
                          <div>
                            <Label className="text-xs">Start Month *</Label>
                            <Input type="month" value={quickEvent.schedule_start_date ? quickEvent.schedule_start_date.substring(0, 7) : ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_start_date: e.target.value + '-01'})} required />
                          </div>
                          <div>
                            <Label className="text-xs">Day of Month *</Label>
                            <Input type="number" min="1" max="31" value={quickEvent.day_of_month || ''} onChange={(e) => setQuickEvent({...quickEvent, day_of_month: parseInt(e.target.value) || 1})} placeholder="13" required />
                          </div>
                          <div>
                            <Label className="text-xs">End Month (optional)</Label>
                            <Input type="month" value={quickEvent.schedule_end_date ? quickEvent.schedule_end_date.substring(0, 7) : ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value + '-01'})} />
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
                
                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="outline" onClick={() => setQuickEventOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white" disabled={selectedMemberIds.length === 0}>
                    Save for {selectedMemberIds.length} Member{selectedMemberIds.length !== 1 ? 's' : ''}
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
        <p className="text-muted-foreground mb-4">{todayTasks.length + birthdaysToday.length} {t('tasks_need_attention')}</p>
      </div>
      
      <Tabs defaultValue="today" className="w-full">
        <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex min-w-full w-max sm:w-full">
            <TabsTrigger value="today" className="flex-shrink-0">
              <Bell className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('today')}</span> ({birthdaysToday.length + todayTasks.length})
            </TabsTrigger>
            <TabsTrigger value="birthday" className="flex-shrink-0">
              🎂 <span className="hidden sm:inline ml-2">{t('birthdays')}</span> ({overdueBirthdays.length})
            </TabsTrigger>
            <TabsTrigger value="followup" className="flex-shrink-0">
              <Hospital className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('followup')}</span> ({griefDue.length + accidentFollowUp.length})
            </TabsTrigger>
            <TabsTrigger value="financial" className="flex-shrink-0">
              <DollarSign className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('aid')}</span> ({financialAidDue.length})
            </TabsTrigger>
            <TabsTrigger value="disconnected" className="flex-shrink-0">
              <Users className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('disconnected')}</span> ({disconnectedMembers.length})
            </TabsTrigger>
            <TabsTrigger value="at-risk" className="flex-shrink-0">
              <AlertTriangle className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('at_risk')}</span> ({atRiskMembers.length})
            </TabsTrigger>
            <TabsTrigger value="upcoming" className="flex-shrink-0">
              <Heart className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('upcoming')}</span> ({upcomingTasks.length})
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
                        <div key={event.id} className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                          <div className="flex items-start gap-3 mb-3">
                            <MemberAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} size="md" />
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
                                {event.completed ? "✅ Birthday contact completed" : "Call to wish happy birthday"}
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
                              <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer">
                                <MessageSquare className="w-4 h-4 mr-1 flex-shrink-0" />
                                <span className="truncate">{t('contact_whatsapp')}</span>
                              </a>
                            </Button>
                            {event.completed ? (
                              <Button size="default" variant="outline" disabled className="bg-green-100 text-green-700 border-green-300 h-11 flex-1 min-w-0">
                                <Check className="w-4 h-4 mr-1" />
                                <span className="truncate">{t('completed')}</span>
                              </Button>
                            ) : (
                              <Button size="default" variant="outline" onClick={() => markBirthdayComplete(event.id, setBirthdaysToday)} className="h-11 flex-1 min-w-0">
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
                          <div key={index} className={`p-4 ${config.bgClass} rounded-lg border ${config.borderClass}`}>
                            <div className="flex items-start gap-3 mb-3">
                              <div className="text-3xl flex-shrink-0">{config.icon}</div>
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
                                  <span className="font-medium">{config.label}:</span> {task.details}
                                </p>
                              </div>
                            </div>
                            
                            {/* Actions - Horizontal compact layout */}
                            <div className="flex gap-2">
                              <Button size="default" className={`${config.btnClass} text-white h-11 flex-1 min-w-0`} asChild>
                                <a href={formatPhoneForWhatsApp(task.member_phone)} target="_blank" rel="noopener noreferrer">
                                  <MessageSquare className="w-4 h-4 mr-1 flex-shrink-0" />
                                  <span className="truncate">{t('contact_whatsapp')}</span>
                                </a>
                              </Button>
                              
                              {task.type === 'financial_aid' ? (
                                // Financial aid: Compact horizontal buttons
                                <>
                                  <Button size="default" variant="outline" onClick={async () => {
                                    try {
                                      await axios.post(`${API}/financial-aid-schedules/${task.data.id}/mark-distributed`);
                                      toast.success('Payment marked as distributed!');
                                      setTodayTasks(prev => prev.filter(t => t.data.id !== task.data.id));
                                    } catch (error) {
                                      toast.error('Failed to mark as distributed');
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
                                          toast.success('Financial aid ignored');
                                          setTodayTasks(prev => prev.filter(t => t.data.id !== task.data.id));
                                        } catch (error) {
                                          toast.error('Failed to ignore');
                                        }
                                      }}>
                                        {t('ignore')}
                                      </DropdownMenuItem>
                                      <DropdownMenuItem 
                                        className="text-red-600"
                                        onClick={async () => {
                                          try {
                                            await axios.post(`${API}/financial-aid-schedules/${task.data.id}/stop`);
                                            toast.success('Schedule stopped');
                                            setTodayTasks(prev => prev.filter(t => t.data.id !== task.data.id));
                                          } catch (error) {
                                            toast.error('Failed to stop');
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
                                    try {
                                      if (task.type === 'grief_support') {
                                        await markGriefStageComplete(task.data.id, setGriefDue);
                                      } else if (task.type === 'accident_followup') {
                                        await axios.post(`${API}/accident-followup/${task.data.id}/complete`);
                                        toast.success('Follow-up marked complete');
                                        setTodayTasks(prev => prev.filter(t => t.data.id !== task.data.id));
                                      }
                                    } catch (error) {
                                      toast.error('Failed to mark as completed');
                                    }
                                  }} className="h-11 flex-1 min-w-0">
                                    <Check className="w-4 h-4 mr-1" />
                                    <span className="truncate">{t('mark_completed')}</span>
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
                                            toast.success('Grief stage ignored');
                                          } else if (task.type === 'accident_followup') {
                                            await axios.post(`${API}/accident-followup/${task.data.id}/ignore`);
                                            toast.success('Accident follow-up ignored');
                                          }
                                          setTodayTasks(prev => prev.filter(t => t.data.id !== task.data.id));
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
        
        
        <TabsContent value="financial" className="space-y-4">
          <Card className="card-border-left-green">
            <CardHeader>
              <CardTitle>{t('financial_aid_overdue')}</CardTitle>
            </CardHeader>
            <CardContent>
              {financialAidDue.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">{t('no_overdue_financial_aid')}</p>
              ) : (
                <div className="space-y-2">
                  {financialAidDue.map(schedule => (
                    <div key={schedule.id} className="p-3 bg-green-50 rounded flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar 
                          member={{name: schedule.member_name, photo_url: schedule.member_photo_url}} 
                          memberId={schedule.member_id} 
                        />
                        <p className="text-sm text-muted-foreground ml-13">
                          {schedule.frequency} - Rp {schedule.aid_amount?.toLocaleString('id-ID')} ({schedule.aid_type})
                        </p>
                        <p className="text-xs ml-13">
                          <span className={schedule.days_overdue > 0 ? 'text-red-600 font-medium' : 'text-green-600'}>
                            {schedule.days_overdue > 0 ? `Overdue ${schedule.days_overdue} days` : 'Due today'} - 
                            Scheduled: {formatDate(schedule.next_occurrence)}
                          </span>
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-green-500 hover:bg-green-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(schedule.member_phone)} target="_blank" rel="noopener noreferrer">
                            Contact
                          </a>
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={async () => {
                            if (window.confirm(`Mark financial aid as distributed to ${schedule.member_name}?`)) {
                              try {
                                await axios.post(`${API}/financial-aid-schedules/${schedule.id}/mark-distributed`);
                                toast.success('Payment distributed! Schedule advanced to next occurrence.');
                                // Update local state
                                setFinancialAidDue(prev => prev.filter(s => s.id !== schedule.id));
                              } catch (error) {
                                toast.error('Failed to mark as distributed');
                              }
                            }
                          }}
                        >
                          {t('mark_distributed')}
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
                                await axios.post(`${API}/financial-aid-schedules/${schedule.id}/ignore`);
                                toast.success('Financial aid schedule ignored');
                                // Update local state
                                setFinancialAidDue(prev => prev.filter(s => s.id !== schedule.id));
                              } catch (error) {
                                toast.error('Failed to ignore');
                              }
                            }}>
                            {t('ignore')}
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              className="text-red-600"
                              onClick={async () => {
                                if (window.confirm(`Stop financial aid schedule for ${schedule.member_name}?`)) {
                                  try {
                                    await axios.post(`${API}/financial-aid-schedules/${schedule.id}/stop`);
                                    toast.success('Schedule stopped');
                                    // Update local state
                                    setFinancialAidDue(prev => prev.filter(s => s.id !== schedule.id));
                                  } catch (error) {
                                    toast.error('Failed to stop schedule');
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
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="disconnected" className="space-y-4">
          <Card className="card-border-left-red">
            <CardHeader>
              <CardTitle>{t('members_disconnected_days', {days: engagementSettings.inactiveDays})}</CardTitle>
            </CardHeader>
            <CardContent>
              {disconnectedMembers.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">No disconnected members</p>
              ) : (
                <div className="space-y-2">
                  {disconnectedMembers.slice(0, 15).map(member => (
                    <div key={member.id} className="p-3 bg-red-50 rounded flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar member={member} memberId={member.id} />
                        <p className="text-sm text-muted-foreground ml-13">{member.days_since_last_contact} days since contact</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-red-500 hover:bg-red-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer">
                            Contact
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => markMemberContacted(member.id, member.name, user, setAtRiskMembers, setDisconnectedMembers)}>
                          {t('mark_contacted')}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="at-risk" className="space-y-4">
          <Card className="card-border-left-amber">
            <CardHeader>
              <CardTitle>{t('members_at_risk_days', {min: engagementSettings.atRiskDays, max: engagementSettings.inactiveDays-1})}</CardTitle>
            </CardHeader>
            <CardContent>
              {atRiskMembers.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">No members at risk</p>
              ) : (
                <div className="space-y-2">
                  {atRiskMembers.map(member => (
                    <div key={member.id} className="p-3 bg-amber-50 rounded flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar member={member} memberId={member.id} />
                        <p className="text-sm text-muted-foreground ml-13">{member.days_since_last_contact} days since contact</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer">
                            Contact
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => markMemberContacted(member.id, member.name, user, setAtRiskMembers, setDisconnectedMembers)}>
                          {t('mark_contacted')}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        

        {/* Birthday Tab - Overdue Birthdays */}
        <TabsContent value="birthday" className="space-y-4">
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
                <div className="space-y-2">
                  {overdueBirthdays
                    .sort((a, b) => (b.days_overdue || 0) - (a.days_overdue || 0))
                    .map(event => (
                    <div key={event.id} className="p-4 bg-amber-50 rounded-lg border border-amber-200 flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} memberId={event.member_id} />
                        <p className="text-sm text-muted-foreground ml-13">
                          {formatDate(event.event_date, 'dd MMM yyyy')} 
                          <span className="ml-2 text-red-600 font-medium">({event.days_overdue} {t('days_ago')})</span>
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer">
                            {t('contact')}
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" onClick={async () => {
                          try {
                            await axios.post(`${API}/care-events/${event.id}/complete`);
                            toast.success('Birthday marked as completed!');
                            // Update local state
                            setOverdueBirthdays(prev => prev.filter(b => b.id !== event.id));
                          } catch (error) {
                            toast.error('Failed to mark as completed');
                          }
                        }}>
                          {t('mark_completed')}
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
                                await axios.post(`${API}/care-events/${event.id}/ignore`);
                                toast.success('Birthday ignored');
                                // Update local state
                                setOverdueBirthdays(prev => prev.filter(b => b.id !== event.id));
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

        <TabsContent value="followup" className="space-y-4">
          {/* Accident/Illness Follow-ups */}
          {hospitalFollowUp.length > 0 && (
            <Card className="card-border-left-blue">
              <CardHeader>
                <CardTitle>Hospital Visit Follow-ups</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {hospitalFollowUp.map(event => (
                    <div key={event.id} className="p-3 bg-blue-50 rounded flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} memberId={event.member_id} />
                        <p className="text-sm text-muted-foreground ml-13">{event.followup_reason}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-blue-500 hover:bg-blue-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer">
                            Contact
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => markAccidentComplete(event.id, setAccidentFollowUp)}>
                          Mark Complete
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
                <div className="space-y-2">
                  {accidentFollowUp.map(followup => (
                    <div key={followup.id} className="p-3 bg-teal-50 rounded flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar member={{name: followup.member_name, photo_url: followup.member_photo_url}} memberId={followup.member_id} />
                        <p className="text-sm text-muted-foreground ml-13">{followup.stage.replace('_', ' ')} - Due: {formatDate(followup.scheduled_date)}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-teal-500 hover:bg-teal-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(followup.member_phone)} target="_blank" rel="noopener noreferrer">
                            Contact
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" onClick={async () => {
                          try {
                            await axios.post(`${API}/accident-followup/${followup.id}/complete`);
                            toast.success('Accident follow-up completed!');
                            // Update local state
                            setAccidentFollowUp(prev => prev.filter(a => a.id !== followup.id));
                          } catch (error) {
                            toast.error('Failed to complete');
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
                                await axios.post(`${API}/accident-followup/${followup.id}/ignore`);
                                toast.success('Accident follow-up ignored');
                                // Update local state
                                setAccidentFollowUp(prev => prev.filter(a => a.id !== followup.id));
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
                <div className="space-y-2">
                  {griefDue.map(stage => (
                    <div key={stage.id} className="p-3 bg-purple-50 rounded flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithAvatar member={{name: stage.member_name, photo_url: stage.member_photo_url}} memberId={stage.member_id} />
                        <p className="text-sm text-muted-foreground ml-13">{stage.stage.replace('_', ' ')} after mourning</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="bg-purple-500 hover:bg-purple-600 text-white" asChild>
                          <a href={formatPhoneForWhatsApp(stage.member_phone)} target="_blank" rel="noopener noreferrer">
                            Contact
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => markGriefStageComplete(stage.id, setGriefDue)}>
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
                                // Update local state
                                setGriefDue(prev => prev.filter(s => s.id !== stage.id));
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
                <div className="space-y-3">
                  {upcomingTasks.map((task, index) => {
                    const taskDate = new Date(task.date);
                    const todayDate = new Date();
                    // Set both to midnight to get accurate day difference
                    taskDate.setHours(0, 0, 0, 0);
                    todayDate.setHours(0, 0, 0, 0);
                    const daysUntil = Math.round((taskDate - todayDate) / (1000 * 60 * 60 * 24));
                    const typeConfig = {
                      birthday: { icon: '🎂', color: 'amber', label: 'Birthday' },
                      grief_support: { icon: '💔', color: 'pink', label: 'Grief Support' },
                      accident_followup: { icon: '🏥', color: 'blue', label: 'Accident Follow-up' },
                      financial_aid: { icon: '💰', color: 'green', label: 'Financial Aid' }
                    };
                    const config = typeConfig[task.type] || { icon: '📋', color: 'gray', label: 'Task' };
                    
                    return (
                      <div key={index} className={`p-4 bg-${config.color}-50 rounded-lg border border-${config.color}-200`}>
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-3 flex-1">
                            <div className="text-2xl">{config.icon}</div>
                            <div className="flex-1">
                              <MemberNameWithAvatar 
                                member={{name: task.member_name, photo_url: task.member_photo_url}} 
                                memberId={task.member_id} 
                              />
                              <p className="text-sm text-muted-foreground">{config.label}: {task.details}</p>
                              <p className="text-xs text-muted-foreground">{formatDate(task.date, 'dd MMM yyyy')}</p>
                            </div>
                            <div className={`px-3 py-1 bg-${config.color}-100 text-${config.color}-700 rounded-full text-sm font-medium`}>
                              {daysUntil} {daysUntil === 1 ? 'day' : 'days'}
                            </div>
                          </div>
                          <div className="flex gap-2 ml-4">
                            <Button size="sm" className={`bg-${config.color}-500 hover:bg-${config.color}-600 text-white`} asChild>
                              <a href={formatPhoneForWhatsApp(task.member_phone)} target="_blank" rel="noopener noreferrer">
                                {t('contact')}
                              </a>
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost">
                                  <MoreVertical className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                {/* Type-specific complete actions */}
                                {task.type === 'financial_aid' && (
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      await axios.post(`${API}/financial-aid-schedules/${task.data.id}/mark-distributed`);
                                      toast.success('Payment distributed!');
                                      setUpcomingTasks(prev => prev.filter((t, i) => i !== index));
                                    } catch (error) {
                                      toast.error('Failed to mark as distributed');
                                    }
                                  }}>
                                    {t('mark_distributed')}
                                  </DropdownMenuItem>
                                )}
                                {task.type === 'grief_support' && (
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      await axios.post(`${API}/grief-support/${task.data.id}/complete`);
                                      toast.success('Grief stage completed!');
                                      setUpcomingTasks(prev => prev.filter((t, i) => i !== index));
                                    } catch (error) {
                                      toast.error('Failed to complete');
                                    }
                                  }}>
                                    Mark Complete
                                  </DropdownMenuItem>
                                )}
                                {task.type === 'accident_followup' && (
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      await axios.post(`${API}/accident-followup/${task.data.id}/complete`);
                                      toast.success('Follow-up completed!');
                                      setUpcomingTasks(prev => prev.filter((t, i) => i !== index));
                                    } catch (error) {
                                      toast.error('Failed to complete');
                                    }
                                  }}>
                                    Mark Complete
                                  </DropdownMenuItem>
                                )}
                                {task.type === 'birthday' && (
                                  <DropdownMenuItem onClick={async () => {
                                    try {
                                      await axios.post(`${API}/care-events/${task.data.id}/complete`);
                                      toast.success('Birthday marked complete!');
                                      setUpcomingTasks(prev => prev.filter((t, i) => i !== index));
                                    } catch (error) {
                                      toast.error('Failed to complete');
                                    }
                                  }}>
                                    Mark Complete
                                  </DropdownMenuItem>
                                )}
                                {/* Ignore option for all types */}
                                <DropdownMenuItem onClick={async () => {
                                  try {
                                    if (task.type === 'grief_support') {
                                      await axios.post(`${API}/grief-support/${task.data.id}/ignore`);
                                      toast.success('Grief stage ignored');
                                    } else if (task.type === 'accident_followup') {
                                      await axios.post(`${API}/accident-followup/${task.data.id}/ignore`);
                                      toast.success('Accident followup ignored');
                                    } else if (task.type === 'financial_aid') {
                                      await axios.post(`${API}/financial-aid-schedules/${task.data.id}/ignore`);
                                      toast.success('Financial aid ignored');
                                    } else if (task.type === 'birthday') {
                                      await axios.post(`${API}/care-events/${task.data.id}/ignore`);
                                      toast.success('Birthday ignored');
                                    }
                                    setUpcomingTasks(prev => prev.filter((t, i) => i !== index));
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