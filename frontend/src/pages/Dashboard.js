import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import LazyImage from '@/components/LazyImage';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Heart, Users, Hospital, Calendar, AlertTriangle, DollarSign, Bell, Plus, Check } from 'lucide-react';

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

const markBirthdayComplete = async (eventId, loadReminders) => {
  try {
    await axios.post(`${API}/care-events/${eventId}/complete`);
    toast.success('Birthday task completed!');
    loadReminders();
  } catch (error) {
    toast.error('Failed to complete');
  }
};

const markGriefStageComplete = async (stageId, loadReminders) => {
  try {
    await axios.post(`${API}/grief-support/${stageId}/complete`);
    toast.success('Grief stage completed!');
    loadReminders();
  } catch (error) {
    toast.error('Failed to complete');
  }
};

const markAccidentComplete = async (eventId, loadReminders) => {
  try {
    await axios.post(`${API}/care-events/${eventId}/complete`);
    toast.success('Accident follow-up completed!');
    loadReminders();
  } catch (error) {
    toast.error('Failed to complete');
  }
};

const markMemberContacted = async (memberId, memberName, user, loadReminders) => {
  try {
    // Create a regular contact event which updates last_contact_date
    await axios.post(`${API}/care-events`, {
      member_id: memberId,
      campus_id: user?.campus_id || '2b3f9094-eef4-4af4-a3ff-730ef4adeb8a', // Use user's campus or default
      event_type: 'regular_contact',
      event_date: new Date().toISOString().split('T')[0],
      title: `Contact with ${memberName}`,
      description: 'Contacted via Reminders page'
    });
    toast.success(`${memberName} marked as contacted! Status updated to Active.`);
    loadReminders(); // Refresh to remove from at-risk/disconnected
  } catch (error) {
    toast.error('Failed to mark as contacted');
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
      toast.error('Select at least one member');
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
              start_date: quickEvent.schedule_start_date,
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

  
  if (loading) return <div>Loading...</div>;
  
  const totalTasks = birthdaysToday.length + griefDue.length + hospitalFollowUp.length + Math.min(atRiskMembers.length, 10);
  
  return (
    <div className="space-y-8 pb-12">
      {/* Welcome Section */}
      <div>
        <h1 className="text-5xl font-playfair font-bold text-foreground mb-2">
          {t('welcome_back')}, {user?.name}!
        </h1>
        <p className="text-muted-foreground text-lg">{t('pastoral_overview')}</p>
      </div>
      
      {/* Stats Cards with Colored Left Borders */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="card-border-left-teal shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">{t('total_members')}</p>
                <p className="text-4xl font-playfair font-bold">805</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-teal-100 flex items-center justify-center">
                <Users className="w-7 h-7 text-teal-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-amber shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">{t('total_interactions')}</p>
                <p className="text-4xl font-playfair font-bold">{birthdaysToday.length + griefToday.length + hospitalFollowUp.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center">
                <Calendar className="w-7 h-7 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-pink shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">{t('pending_reminders')}</p>
                <p className="text-4xl font-playfair font-bold">{griefDue.length + financialAidDue.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-pink-100 flex items-center justify-center">
                <Bell className="w-7 h-7 text-pink-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-purple shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">{t('at_risk_disconnected')}</p>
                <p className="text-4xl font-playfair font-bold">{atRiskMembers.length + disconnectedMembers.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-purple-100 flex items-center justify-center">
                <Heart className="w-7 h-7 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Quick Actions */}
      <div>
        <h2 className="text-2xl font-playfair font-bold mb-4">{t('quick_actions')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Dialog open={quickEventOpen} onOpenChange={setQuickEventOpen}>
            <DialogTrigger asChild>
              <Button className="w-full h-14 bg-teal-500 hover:bg-teal-600 text-white text-base font-semibold">
                <Plus className="w-5 h-5 mr-2" />{t('add_new_care_event')}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Quick Care Event (Multi-Member)</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleQuickEvent} className="space-y-6">
                {/* Member Selection */}
                <div className="space-y-3">
                  <Label>Select Members *</Label>
                  <Input
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder="Type member name to search..."
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
                    <Label>Event Type *</Label>
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
                      <Label>Event Date *</Label>
                      <Input type="date" value={quickEvent.event_date} onChange={(e) => setQuickEvent({...quickEvent, event_date: e.target.value})} required />
                    </div>
                  )}
                </div>
                
                <div>
                  <Label>Description</Label>
                  <Input value={quickEvent.description} onChange={(e) => setQuickEvent({...quickEvent, description: e.target.value})} placeholder="Additional details..." />
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
                        <div className="grid grid-cols-3 gap-3 p-3 bg-blue-50 rounded">
                          <div>
                            <Label className="text-xs">Start Date</Label>
                            <Input type="date" value={quickEvent.schedule_start_date || ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_start_date: e.target.value})} />
                          </div>
                          <div>
                            <Label className="text-xs">Day of Week</Label>
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
                            <Label className="text-xs">End Date</Label>
                            <Input type="date" value={quickEvent.schedule_end_date || ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value})} />
                          </div>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'monthly' && (
                        <div className="grid grid-cols-3 gap-3 p-3 bg-purple-50 rounded">
                          <div>
                            <Label className="text-xs">Start Month</Label>
                            <Input type="month" value={quickEvent.schedule_start_date ? quickEvent.schedule_start_date.substring(0, 7) : ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_start_date: e.target.value + '-01'})} />
                          </div>
                          <div>
                            <Label className="text-xs">Day of Month</Label>
                            <Input type="number" min="1" max="31" value={quickEvent.day_of_month || ''} onChange={(e) => setQuickEvent({...quickEvent, day_of_month: parseInt(e.target.value) || 1})} placeholder="13" />
                          </div>
                          <div>
                            <Label className="text-xs">End Month</Label>
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
      
      {/* AI-Powered Suggestions */}
      {suggestions.length > 0 && (
        <Card className="card-border-left-purple shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl font-playfair flex items-center gap-2">
              🤖 {t('ai_pastoral_recommendations')} ({suggestions.length})
            </CardTitle>
            <p className="text-sm text-muted-foreground">{t('intelligent_followup')}</p>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {suggestions.slice(0, 8).map((suggestion) => (
                <div key={`${suggestion.member_id}-${suggestion.suggestion}`} className={`p-3 rounded-lg border ${
                  (suggestion.priority || 'medium') === 'high' ? 'bg-red-50 border-red-200' :
                  (suggestion.priority || 'medium') === 'medium' ? 'bg-amber-50 border-amber-200' :
                  'bg-blue-50 border-blue-200'
                }`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <MemberNameWithAvatar 
                          member={{name: suggestion.member_name, photo_url: suggestion.member_photo_url}} 
                          memberId={suggestion.member_id} 
                        />
                        <span className={`text-xs px-2 py-1 rounded font-medium ${
                          (suggestion.priority || 'medium') === 'high' ? 'bg-red-100 text-red-700' :
                          (suggestion.priority || 'medium') === 'medium' ? 'bg-amber-100 text-amber-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {suggestion.priority?.toUpperCase() || 'MEDIUM'} PRIORITY
                        </span>
                      </div>
                      <p className="font-semibold text-sm ml-13">{suggestion.suggestion}</p>
                      <p className="text-xs text-muted-foreground ml-13">{suggestion.reason}</p>
                      <p className="text-xs text-green-700 ml-13 mt-1">💡 {suggestion.recommended_action}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" className="bg-purple-500 hover:bg-purple-600 text-white" asChild>
                        <a href={formatPhoneForWhatsApp(suggestion.member_phone)} target="_blank" rel="noopener noreferrer">
                          Contact
                        </a>
                      </Button>
                      <Button size="sm" variant="outline" onClick={async () => {
                        try {
                          // Mark suggestion as acted upon by creating contact event
                          await axios.post(`${API}/care-events`, {
                            member_id: suggestion.member_id,
                            campus_id: user?.campus_id || '2b3f9094-eef4-4af4-a3ff-730ef4adeb8a',
                            event_type: 'regular_contact',
                            event_date: new Date().toISOString().split('T')[0],
                            title: 'AI Suggestion Follow-up',
                            description: `Acted on AI suggestion: ${suggestion.suggestion}`
                          });
                          toast.success(`${suggestion.member_name} marked as contacted!`);
                          loadReminders(); // Refresh to remove from suggestions
                        } catch (error) {
                          toast.error('Failed to mark as completed');
                        }
                      }}>
                        {t('mark_completed')}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Task Management */}
      <div>
        <h2 className="text-2xl font-playfair font-bold mb-4">{t('todays_tasks_reminders')}</h2>
        <p className="text-muted-foreground mb-4">{todayTasks.length + birthdaysToday.length} {t('tasks_need_attention')}</p>
      </div>
      
      <Tabs defaultValue="today" className="w-full">
        <div className="overflow-x-auto">
          <TabsList className="inline-flex w-max min-w-full">
            <TabsTrigger value="today" className="whitespace-nowrap">
              <Calendar className="w-4 h-4 mr-2" />Today ({birthdaysToday.length + griefToday.length})
            </TabsTrigger>
            <TabsTrigger value="birthday" className="whitespace-nowrap">
              🎂 Birthdays ({overdueBirthdays.length})
            </TabsTrigger>
            <TabsTrigger value="followup" className="whitespace-nowrap">
              <Hospital className="w-4 h-4 mr-2" />Follow-up ({hospitalFollowUp.length + griefDue.length + accidentFollowUp.length})
            </TabsTrigger>
            <TabsTrigger value="financial" className="whitespace-nowrap">
              <DollarSign className="w-4 h-4 mr-2" />Aid ({financialAidDue.length})
            </TabsTrigger>
            <TabsTrigger value="disconnected" className="whitespace-nowrap">
              <Users className="w-4 h-4 mr-2" />Disconnected ({disconnectedMembers.length})
            </TabsTrigger>
            <TabsTrigger value="at-risk" className="whitespace-nowrap">
              <AlertTriangle className="w-4 h-4 mr-2" />At Risk ({atRiskMembers.length})
            </TabsTrigger>
            <TabsTrigger value="upcoming" className="whitespace-nowrap">
              <Heart className="w-4 h-4 mr-2" />Upcoming ({upcomingBirthdays.length})
            </TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="today" className="space-y-4">
          {birthdaysToday.length === 0 && todayTasks.length === 0 ? (
            <Card><CardContent className="p-6 text-center">No urgent tasks for today! 🎉</CardContent></Card>
          ) : (
            <>
              {/* Birthdays Today */}
              {birthdaysToday.length > 0 && (
                <Card className="card-border-left-amber">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      🎂 Birthdays Today ({birthdaysToday.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {birthdaysToday.map(event => (
                        <div key={event.id} className="p-3 bg-amber-50 rounded flex justify-between items-center">
                          <div className="flex-1">
                            <MemberNameWithAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} memberId={event.member_id} />
                            <p className="text-sm text-muted-foreground ml-13">
                              {event.completed ? "Birthday contact completed ✅" : "Call to wish happy birthday"}
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" asChild>
                              <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer">
                                Contact
                              </a>
                            </Button>
                            {event.completed ? (
                              <Button size="sm" variant="outline" disabled className="bg-green-100 text-green-700 border-green-300">
                                <Check className="w-4 h-4" />
                                Completed
                              </Button>
                            ) : (
                              <Button size="sm" variant="outline" onClick={() => markBirthdayComplete(event.id, loadReminders)}>
                                Mark Complete
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
                <Card>
                  <CardHeader>
                    <CardTitle>Other Tasks Due Today ({todayTasks.length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {todayTasks.map((task, index) => {
                        const typeConfig = {
                          grief_support: { icon: '💔', color: 'pink', label: 'Grief Support' },
                          accident_followup: { icon: '🏥', color: 'blue', label: 'Accident Follow-up' },
                          financial_aid: { icon: '💰', color: 'green', label: 'Financial Aid' }
                        };
                        const config = typeConfig[task.type] || { icon: '📋', color: 'gray', label: 'Task' };
                        
                        return (
                          <div key={index} className={`p-4 bg-${config.color}-50 rounded-lg border border-${config.color}-200 flex justify-between items-center`}>
                            <div className="flex items-center gap-3 flex-1">
                              <div className="text-2xl">{config.icon}</div>
                              <div className="flex-1">
                                <MemberNameWithAvatar 
                                  member={{name: task.member_name, photo_url: task.member_photo_url}} 
                                  memberId={task.member_id} 
                                />
                                <p className="text-sm text-muted-foreground">{config.label}: {task.details}</p>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" className={`bg-${config.color}-500 hover:bg-${config.color}-600 text-white`} asChild>
                                <a href={formatPhoneForWhatsApp(task.member_phone)} target="_blank" rel="noopener noreferrer">
                                  {t('contact')}
                                </a>
                              </Button>
                              <Button size="sm" variant="outline" onClick={async () => {
                                try {
                                  if (task.type === 'grief_support') {
                                    await markGriefStageComplete(task.data.id, loadReminders);
                                  } else if (task.type === 'accident_followup') {
                                    await axios.post(`${API}/accident-followup/${task.data.id}/complete`);
                                    toast.success('Follow-up marked complete');
                                    loadReminders();
                                  }
                                } catch (error) {
                                  toast.error('Failed to mark as completed');
                                }
                              }}>
                                {t('mark_completed')}
                              </Button>
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
              <CardTitle>Financial Aid Due Today</CardTitle>
            </CardHeader>
            <CardContent>
              {financialAidDue.length === 0 ? (
                <p className="text-center text-muted-foreground py-6">No financial aid scheduled for today</p>
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
                                loadReminders();
                              } catch (error) {
                                toast.error('Failed to mark as distributed');
                              }
                            }
                          }}
                        >
                          Mark Distributed
                        </Button>
                        <Button 
                          size="sm" 
                          variant="ghost" 
                          className="text-red-600"
                          onClick={async () => {
                            if (window.confirm(`Stop financial aid schedule for ${schedule.member_name}?`)) {
                              try {
                                await axios.post(`${API}/financial-aid-schedules/${schedule.id}/stop`);
                                toast.success('Schedule stopped');
                                loadReminders();
                              } catch (error) {
                                toast.error('Failed to stop schedule');
                              }
                            }
                          }}
                        >
                          Stop Schedule
                        </Button>
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
              <CardTitle>Members Disconnected ({engagementSettings.inactiveDays}+ days no contact)</CardTitle>
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
                        <Button size="sm" variant="outline" onClick={() => markMemberContacted(member.id, member.name, user, loadReminders)}>
                          Mark Contacted
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
              <CardTitle>Members at Risk ({engagementSettings.atRiskDays}-{engagementSettings.inactiveDays-1} days no contact)</CardTitle>
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
                        <Button size="sm" variant="outline" onClick={() => markMemberContacted(member.id, member.name, user, loadReminders)}>
                          Mark Contacted
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
                No overdue birthdays - all caught up! 🎉
              </CardContent>
            </Card>
          ) : (
            <Card className="border-amber-200">
              <CardHeader>
                <CardTitle>🎂 Overdue Birthdays ({overdueBirthdays.length})</CardTitle>
                <CardDescription>Birthdays that passed but haven't been acknowledged yet</CardDescription>
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
                          <span className="ml-2 text-red-600 font-medium">({event.days_overdue} days ago)</span>
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
                            loadReminders();
                          } catch (error) {
                            toast.error('Failed to mark as completed');
                          }
                        }}>
                          {t('mark_completed')}
                        </Button>
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
                        <Button size="sm" variant="outline" onClick={() => markAccidentComplete(event.id, loadReminders)}>
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
                <CardTitle>Accident/Illness Recovery Follow-ups</CardTitle>
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
                            loadReminders();
                          } catch (error) {
                            toast.error('Failed to complete');
                          }
                        }}>
                          Mark Complete
                        </Button>
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
                <CardTitle>Grief Support Follow-ups</CardTitle>
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
                        <Button size="sm" variant="outline" onClick={() => markGriefStageComplete(stage.id, loadReminders)}>
                          Mark Complete
                        </Button>
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
                No upcoming tasks in the next 7 days
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Upcoming Tasks (Next 7 Days)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {upcomingTasks.map((task, index) => {
                    const daysUntil = Math.ceil((new Date(task.date) - new Date()) / (1000 * 60 * 60 * 24));
                    const typeConfig = {
                      birthday: { icon: '🎂', color: 'amber', label: 'Birthday' },
                      grief_support: { icon: '💔', color: 'pink', label: 'Grief Support' },
                      accident_followup: { icon: '🏥', color: 'blue', label: 'Accident Follow-up' },
                      financial_aid: { icon: '💰', color: 'green', label: 'Financial Aid' }
                    };
                    const config = typeConfig[task.type] || { icon: '📋', color: 'gray', label: 'Task' };
                    
                    return (
                      <div key={index} className={`p-4 bg-${config.color}-50 rounded-lg border border-${config.color}-200 flex justify-between items-center`}>
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