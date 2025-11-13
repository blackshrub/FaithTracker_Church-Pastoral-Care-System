import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Users, Heart, AlertTriangle, DollarSign, Plus, UserPlus, Bell, Calendar, Zap, Hospital } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatDate = (dateStr) => {
  try {
    return new Date(dateStr).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
  } catch { return dateStr; }
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
      <Avatar className="w-10 h-10">
        {photoUrl && <AvatarImage src={photoUrl} alt={member.name} className="object-cover" />}
        <AvatarFallback className="bg-teal-100 text-teal-700 font-semibold text-xs">
          {getInitials(member.name)}
        </AvatarFallback>
      </Avatar>
      <div>
        <p className="font-semibold hover:underline">{member.name}</p>
      </div>
    </Link>
  );
};

export const Dashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [birthdaysToday, setBirthdaysToday] = useState([]);
  const [griefToday, setGriefToday] = useState([]);
  const [griefDue, setGriefDue] = useState([]);
  const [hospitalFollowUp, setHospitalFollowUp] = useState([]);
  const [atRiskMembers, setAtRiskMembers] = useState([]);
  const [disconnectedMembers, setDisconnectedMembers] = useState([]);
  const [upcomingBirthdays, setUpcomingBirthdays] = useState([]);
  const [financialAidDue, setFinancialAidDue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [quickEventOpen, setQuickEventOpen] = useState(false);
  const [allMembers, setAllMembers] = useState([]);
  const [selectedMemberIds, setSelectedMemberIds] = useState([]);
  const [memberSearch, setMemberSearch] = useState('');
  const [engagementSettings, setEngagementSettings] = useState({
    atRiskDays: 60,
    inactiveDays: 90
  });
  const [quickEvent, setQuickEvent] = useState({
    event_type: 'regular_contact',
    event_date: new Date().toISOString().split('T')[0],
    title: '',
    description: '',
    aid_type: 'education',
    aid_amount: '',
    grief_relationship: '',
    hospital_name: '',
    // Financial aid scheduling
    schedule_frequency: 'one_time',
    schedule_start_date: new Date().toISOString().split('T')[0],
    schedule_end_date: '',
    day_of_week: 'monday',
    day_of_month: 1,
    month_of_year: 1
  });
  
  useEffect(() => {
    // Load engagement settings from localStorage (set in Settings page)
    const savedSettings = localStorage.getItem('engagement_settings');
    if (savedSettings) {
      setEngagementSettings(JSON.parse(savedSettings));
    }
    loadDashboardData();
    loadMembers();
  }, []);
  
  const loadMembers = async () => {
    try {
      const response = await axios.get(`${API}/members`);
      setAllMembers(response.data);
    } catch (error) {
      console.error('Error loading members');
    }
  };
  
  const loadDashboardData = async () => {
    try {
      const today = new Date().toISOString().split('T')[0];
      const weekAhead = new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0];
      
      const [statsRes, eventsRes, griefRes, hospitalRes, atRiskRes, membersRes, aidDueRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`),
        axios.get(`${API}/care-events`),
        axios.get(`${API}/grief-support?completed=false`),
        axios.get(`${API}/care-events/hospital/due-followup`),
        axios.get(`${API}/members/at-risk`),
        axios.get(`${API}/members`),
        axios.get(`${API}/financial-aid-schedules/due-today`)
      ]);
      
      setStats(statsRes.data);
      
      // Get member names, phones, and photos for events
      const memberMap = {};
      membersRes.data.forEach(m => memberMap[m.id] = { 
        name: m.name, 
        phone: m.phone, 
        photo_url: m.photo_url 
      });
      
      // Filter birthdays for today with member names and photos
      const todayBirthdays = eventsRes.data.filter(e => 
        e.event_type === 'birthday' && e.event_date === today
      ).map(e => ({...e, member_name: memberMap[e.member_id]?.name, member_phone: memberMap[e.member_id]?.phone, member_photo_url: memberMap[e.member_id]?.photo_url}));
      
      // Get upcoming birthdays with member names and photos
      const upcoming = eventsRes.data.filter(e => 
        e.event_type === 'birthday' && 
        e.event_date > today && 
        e.event_date <= weekAhead
      ).map(e => ({...e, member_name: memberMap[e.member_id]?.name, member_phone: memberMap[e.member_id]?.phone, member_photo_url: memberMap[e.member_id]?.photo_url}));
      
      // Filter grief stages due today AND overdue (for follow-up tab)
      const griefToday = griefRes.data.filter(g => g.scheduled_date === today).map(g => ({
        ...g,
        member_name: memberMap[g.member_id]?.name,
        member_phone: memberMap[g.member_id]?.phone,
        member_photo_url: memberMap[g.member_id]?.photo_url
      }));
      
      // Filter overdue grief stages for follow-up tab
      const griefOverdue = griefRes.data.filter(g => {
        const schedDate = new Date(g.scheduled_date);
        return schedDate <= new Date() && !g.completed;
      }).map(g => ({
        ...g,
        member_name: memberMap[g.member_id]?.name,
        member_phone: memberMap[g.member_id]?.phone,
        member_photo_url: memberMap[g.member_id]?.photo_url
      }));
      
      // Separate at-risk and disconnected based on Settings thresholds
      const atRisk = atRiskRes.data.filter(m => 
        m.days_since_last_contact >= engagementSettings.atRiskDays && 
        m.days_since_last_contact < engagementSettings.inactiveDays
      );
      const disconnected = atRiskRes.data.filter(m => 
        m.days_since_last_contact >= engagementSettings.inactiveDays
      );
      
      setBirthdaysToday(todayBirthdays);
      setUpcomingBirthdays(upcoming);
      setGriefToday(griefToday);
      setGriefDue(griefOverdue);
      setHospitalFollowUp(hospitalRes.data.map(h => ({...h, member_name: memberMap[h.member_id]?.name, member_phone: memberMap[h.member_id]?.phone, member_photo_url: memberMap[h.member_id]?.photo_url})));
      setFinancialAidDue(aidDueRes.data);
      setAtRiskMembers(atRisk);
      setDisconnectedMembers(disconnected);
    } catch (error) {
      toast.error('Failed to load');
    } finally {
      setLoading(false);
    }
  };
  
  const markBirthdayComplete = async (eventId) => {
    try {
      await axios.post(`${API}/care-events/${eventId}/complete`);
      toast.success('Birthday task completed!');
      loadDashboardData();
    } catch (error) {
      toast.error('Failed to complete');
    }
  };
  
  const markGriefStageComplete = async (stageId) => {
    try {
      await axios.post(`${API}/grief-support/${stageId}/complete`);
      toast.success('Grief stage completed!');
      loadDashboardData();
    } catch (error) {
      toast.error('Failed to complete');
    }
  };
  
  const markMemberContacted = async (memberId, memberName) => {
    try {
      await axios.post(`${API}/care-events`, {
        member_id: memberId,
        campus_id: user?.campus_id || '2b3f9094-eef4-4af4-a3ff-730ef4adeb8a',
        event_type: 'regular_contact',
        event_date: new Date().toISOString().split('T')[0],
        title: `Contact with ${memberName}`,
        description: 'Contacted via Dashboard'
      });
      toast.success(`${memberName} marked as contacted! Status updated to Active.`);
      loadDashboardData();
    } catch (error) {
      toast.error('Failed to mark as contacted');
    }
  };
  
  const handleQuickEvent = async (e) => {
    e.preventDefault();
    if (selectedMemberIds.length === 0) {
      toast.error('Select at least one member');
      return;
    }
    
    try {
      let success = 0;
      for (const memberId of selectedMemberIds) {
        const member = allMembers.find(m => m.id === memberId);
        await axios.post(`${API}/care-events`, {
          member_id: memberId,
          campus_id: member.campus_id,  // Use member's campus_id
          ...quickEvent,
          aid_amount: quickEvent.aid_amount ? parseFloat(quickEvent.aid_amount) : null
        });
        success++;
      }
      toast.success(`Added care event for ${success} members!`);
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
        mourning_service_date: '',
        hospital_name: '',
        admission_date: ''
      });
      loadDashboardData();
    } catch (error) {
      toast.error('Failed to add events');
    }
  };
  
  const toggleMemberSelection = (memberId) => {
    setSelectedMemberIds(prev => 
      prev.includes(memberId) ? prev.filter(id => id !== memberId) : [...prev, memberId]
    );
    // Clear search field after selection
    setMemberSearch('');
  };
  
  const filteredMembers = allMembers.filter(m => 
    m.name.toLowerCase().includes(memberSearch.toLowerCase())
  );
  
  return (
    <div className="space-y-8 pb-12">
      {/* Welcome Section */}
      <div>
        <h1 className="text-5xl font-playfair font-bold text-foreground mb-2">
          Welcome back, {user?.name}!
        </h1>
        <p className="text-muted-foreground text-lg">Here's your pastoral care overview</p>
      </div>
      
      {/* Stats Cards with Colored Left Borders */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="card-border-left-teal shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Total Members</p>
                <p className="text-4xl font-playfair font-bold">{stats?.total_members || 0}</p>
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
                <p className="text-sm text-muted-foreground mb-1">Total Interactions</p>
                <p className="text-4xl font-playfair font-bold">{recentActivity.length}</p>
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
                <p className="text-sm text-muted-foreground mb-1">Pending Reminders</p>
                <p className="text-4xl font-playfair font-bold">{stats?.active_grief_support || 0}</p>
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
                <p className="text-sm text-muted-foreground mb-1">Upcoming Occasions</p>
                <p className="text-4xl font-playfair font-bold">{upcomingEvents.length}</p>
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
        <h2 className="text-2xl font-playfair font-bold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Dialog open={quickEventOpen} onOpenChange={setQuickEventOpen}>
            <DialogTrigger asChild>
              <Button className="w-full h-14 bg-teal-500 hover:bg-teal-600 text-white text-base font-semibold">
                <Plus className="w-5 h-5 mr-2" />Add New Care Event
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Quick Care Event (Multi-Member)</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleQuickEvent} className="space-y-6">
                {/* Member Selection with Better UX */}
                <div className="space-y-3">
                  <Label>Select Members *</Label>
                  <Input
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder="Type member name to search..."
                  />
                  
                  {/* Selected Members Display */}
                  {selectedMemberIds.length > 0 && (
                    <div className="p-3 bg-teal-50 rounded border">
                      <p className="font-semibold text-sm mb-2">Selected Members ({selectedMemberIds.length}):</p>
                      <div className="flex flex-wrap gap-2">
                        {selectedMemberIds.map(id => {
                          const member = allMembers.find(m => m.id === id);
                          return member ? (
                            <span key={id} className="bg-teal-100 text-teal-800 px-2 py-1 rounded text-xs flex items-center gap-1">
                              {member.name}
                              <button type="button" onClick={() => toggleMemberSelection(id)} className="ml-1 text-teal-600 hover:text-teal-800">×</button>
                            </span>
                          ) : null;
                        })}
                      </div>
                    </div>
                  )}
                  
                  {/* Member Search Results */}
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
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <Label>Event Type *</Label>
                    <Select value={quickEvent.event_type} onValueChange={(v) => setQuickEvent({...quickEvent, event_type: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="childbirth">👶 Childbirth</SelectItem>
                        <SelectItem value="financial_aid">💰 Financial Aid</SelectItem>
                        <SelectItem value="grief_loss">💔 Grief/Loss</SelectItem>
                        <SelectItem value="new_house">🏠 New House</SelectItem>
                        <SelectItem value="accident_illness">🚑 Accident/Illness</SelectItem>
                        <SelectItem value="regular_contact">📞 Regular Contact</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {quickEvent.event_type !== 'financial_aid' && (
                    <div>
                      <Label>Date *</Label>
                      <Input type="date" value={quickEvent.event_date} onChange={(e) => setQuickEvent({...quickEvent, event_date: e.target.value})} required />
                    </div>
                  )}
                </div>
                
                <div>
                  <Label>Title *</Label>
                  <Input value={quickEvent.title} onChange={(e) => setQuickEvent({...quickEvent, title: e.target.value})} placeholder="e.g., Financial assistance for 15 families" required />
                </div>
                
                <div>
                  <Label>Description</Label>
                  <Input value={quickEvent.description} onChange={(e) => setQuickEvent({...quickEvent, description: e.target.value})} placeholder="Additional details..." />
                </div>
                
                {/* Conditional Fields Based on Event Type */}
                {quickEvent.event_type === 'financial_aid' && (
                  <div className="space-y-4 p-4 bg-green-50 rounded border border-green-200">
                    <h4 className="font-semibold text-green-900">Financial Aid Details</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Aid Type *</Label>
                        <Select value={quickEvent.aid_type} onValueChange={(v) => setQuickEvent({...quickEvent, aid_type: v})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="education">Education Support</SelectItem>
                            <SelectItem value="medical">Medical Bills</SelectItem>
                            <SelectItem value="emergency">Emergency Relief</SelectItem>
                            <SelectItem value="housing">Housing Assistance</SelectItem>
                            <SelectItem value="food">Food Support</SelectItem>
                            <SelectItem value="funeral_costs">Funeral Costs</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Amount per Member (Rp) *</Label>
                        <Input type="number" value={quickEvent.aid_amount} onChange={(e) => setQuickEvent({...quickEvent, aid_amount: e.target.value})} placeholder="1500000" required />
                      </div>
                    </div>
                    <p className="text-sm text-green-700">
                      Total: Rp {((quickEvent.aid_amount || 0) * selectedMemberIds.length).toLocaleString('id-ID')} for {selectedMemberIds.length} members
                    </p>
                    
                    {/* Financial Aid Scheduling */}
                    <div className="space-y-4 border-t pt-4">
                      <h5 className="font-semibold text-green-800">📅 Aid Schedule</h5>
                      <div>
                        <Label>Frequency *</Label>
                        <Select value={quickEvent.schedule_frequency} onValueChange={(v) => setQuickEvent({...quickEvent, schedule_frequency: v})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="one_time">One-time (today only)</SelectItem>
                            <SelectItem value="weekly">Weekly (every week)</SelectItem>
                            <SelectItem value="monthly">Monthly (every month)</SelectItem>
                            <SelectItem value="annually">Annually (every year)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      {quickEvent.schedule_frequency === 'weekly' && (
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <Label className="text-xs">Start Date</Label>
                            <Input type="date" value={quickEvent.schedule_start_date} onChange={(e) => setQuickEvent({...quickEvent, schedule_start_date: e.target.value})} />
                          </div>
                          <div>
                            <Label className="text-xs">Day</Label>
                            <Select value={quickEvent.day_of_week} onValueChange={(v) => setQuickEvent({...quickEvent, day_of_week: v})}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="monday">Mon</SelectItem>
                                <SelectItem value="tuesday">Tue</SelectItem>
                                <SelectItem value="wednesday">Wed</SelectItem>
                                <SelectItem value="thursday">Thu</SelectItem>
                                <SelectItem value="friday">Fri</SelectItem>
                                <SelectItem value="saturday">Sat</SelectItem>
                                <SelectItem value="sunday">Sun</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs">End (optional)</Label>
                            <Input type="date" value={quickEvent.schedule_end_date} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value})} />
                          </div>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'monthly' && (
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <Label className="text-xs">Start</Label>
                            <Input type="month" value={quickEvent.schedule_start_date.substring(0, 7)} onChange={(e) => setQuickEvent({...quickEvent, schedule_start_date: e.target.value + '-01'})} />
                          </div>
                          <div>
                            <Label className="text-xs">Day of Month</Label>
                            <Input type="number" min="1" max="31" value={quickEvent.day_of_month} onChange={(e) => setQuickEvent({...quickEvent, day_of_month: parseInt(e.target.value)})} />
                          </div>
                          <div>
                            <Label className="text-xs">End (optional)</Label>
                            <Input type="month" value={quickEvent.schedule_end_date ? quickEvent.schedule_end_date.substring(0, 7) : ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value + '-01'})} />
                          </div>
                        </div>
                      )}
                      
                      {quickEvent.schedule_frequency === 'annually' && (
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <Label className="text-xs">Month</Label>
                            <Select value={quickEvent.month_of_year.toString()} onValueChange={(v) => setQuickEvent({...quickEvent, month_of_year: parseInt(v)})}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="1">Jan</SelectItem>
                                <SelectItem value="2">Feb</SelectItem>
                                <SelectItem value="3">Mar</SelectItem>
                                <SelectItem value="4">Apr</SelectItem>
                                <SelectItem value="5">May</SelectItem>
                                <SelectItem value="6">Jun</SelectItem>
                                <SelectItem value="7">Jul</SelectItem>
                                <SelectItem value="8">Aug</SelectItem>
                                <SelectItem value="9">Sep</SelectItem>
                                <SelectItem value="10">Oct</SelectItem>
                                <SelectItem value="11">Nov</SelectItem>
                                <SelectItem value="12">Dec</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs">End Year</Label>
                            <Input type="number" min={new Date().getFullYear()} value={quickEvent.schedule_end_date ? new Date(quickEvent.schedule_end_date).getFullYear() : ''} onChange={(e) => setQuickEvent({...quickEvent, schedule_end_date: e.target.value ? `${e.target.value}-12-31` : ''})} />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {quickEvent.event_type === 'grief_loss' && (
                  <div className="space-y-4 p-4 bg-purple-50 rounded border border-purple-200">
                    <h4 className="font-semibold text-purple-900">⭐ Grief Support (Auto-generates 6-stage timeline)</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Relationship to Deceased *</Label>
                        <Select value={quickEvent.grief_relationship || ''} onValueChange={(v) => setQuickEvent({...quickEvent, grief_relationship: v})}>
                          <SelectTrigger><SelectValue placeholder="Select relationship" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="spouse">Spouse</SelectItem>
                            <SelectItem value="parent">Parent</SelectItem>
                            <SelectItem value="child">Child</SelectItem>
                            <SelectItem value="sibling">Sibling</SelectItem>
                            <SelectItem value="other">Other</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Mourning Service Date *</Label>
                        <Input type="date" value={quickEvent.mourning_service_date || ''} onChange={(e) => setQuickEvent({...quickEvent, mourning_service_date: e.target.value})} required />
                      </div>
                    </div>
                  </div>
                )}
                
                {quickEvent.event_type === 'hospital_visit' && (
                  <div className="space-y-4 p-4 bg-blue-50 rounded border border-blue-200">
                    <h4 className="font-semibold text-blue-900">Hospital Visit Details</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Hospital Name</Label>
                        <Input value={quickEvent.hospital_name || ''} onChange={(e) => setQuickEvent({...quickEvent, hospital_name: e.target.value})} placeholder="RSU Jakarta" />
                      </div>
                      <div>
                        <Label>Admission Date</Label>
                        <Input type="date" value={quickEvent.admission_date || ''} onChange={(e) => setQuickEvent({...quickEvent, admission_date: e.target.value})} />
                      </div>
                    </div>
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
          <Link to="/reminders">
            <Button className="w-full h-14 bg-amber-500 hover:bg-amber-600 text-white text-base font-semibold">
              <Bell className="w-5 h-5 mr-2" />View Reminders
            </Button>
          </Link>
        </div>
      </div>
      
      {/* Task Management Tabs (formerly Reminders page) */}
      <div>
        <h2 className="text-2xl font-playfair font-bold mb-4">Today's Tasks & Reminders</h2>
        
        <Tabs defaultValue="today" className="w-full">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="today">
              <Calendar className="w-4 h-4 mr-2" />Today ({birthdaysToday.length + griefToday.length})
            </TabsTrigger>
            <TabsTrigger value="followup">
              <Hospital className="w-4 h-4 mr-2" />Follow-up ({hospitalFollowUp.length + griefDue.length})
            </TabsTrigger>
            <TabsTrigger value="financial">
              <DollarSign className="w-4 h-4 mr-2" />Financial Aid ({financialAidDue.length})
            </TabsTrigger>
            <TabsTrigger value="disconnected">
              <Users className="w-4 h-4 mr-2" />Disconnected ({disconnectedMembers.length})
            </TabsTrigger>
            <TabsTrigger value="at-risk">
              <AlertTriangle className="w-4 h-4 mr-2" />At Risk ({atRiskMembers.length})
            </TabsTrigger>
            <TabsTrigger value="upcoming">
              <Heart className="w-4 h-4 mr-2" />Upcoming ({upcomingBirthdays.length})
            </TabsTrigger>
          </TabsList>
          
          {/* Today Tab */}
          <TabsContent value="today" className="space-y-4">
            {birthdaysToday.length === 0 && griefToday.length === 0 ? (
              <Card><CardContent className="p-6 text-center">No urgent tasks for today! 🎉</CardContent></Card>
            ) : (
              <>
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
                              <p className="text-sm text-muted-foreground ml-13">Call to wish happy birthday</p>
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" asChild>
                                <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer">
                                  Contact
                                </a>
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => markBirthdayComplete(event.id)}>
                                Mark Complete
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
                
                {griefToday.length > 0 && (
                  <Card className="card-border-left-pink">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        💔 Grief Support Due Today ({griefToday.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {griefToday.map(stage => (
                          <div key={stage.id} className="p-3 bg-pink-50 rounded flex justify-between items-center">
                            <div className="flex-1">
                              <MemberNameWithAvatar member={{name: stage.member_name, photo_url: stage.member_photo_url}} memberId={stage.member_id} />
                              <p className="text-sm text-muted-foreground ml-13">{stage.stage.replace('_', ' ')} stage</p>
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" className="bg-pink-500 hover:bg-pink-600 text-white" asChild>
                                <a href={formatPhoneForWhatsApp(stage.member_phone)} target="_blank" rel="noopener noreferrer">
                                  Contact
                                </a>
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => markGriefStageComplete(stage.id)}>
                                Mark Complete
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </TabsContent>
          
          {/* All other tabs... (continuing in next message due to length) */}
          
          {/* Follow-up Tab */}
          <TabsContent value="followup" className="space-y-4">
            {/* Accident/Illness Follow-ups */}
            {hospitalFollowUp.length > 0 && (
              <Card className="card-border-left-blue">
                <CardHeader><CardTitle>Accident/Illness Follow-ups</CardTitle></CardHeader>
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
                            <a href={formatPhoneForWhatsApp(event.member_phone)} target="_blank" rel="noopener noreferrer">Contact</a>
                          </Button>
                          <Button size="sm" variant="outline" onClick={async () => {
                            try {
                              await axios.post(`${API}/care-events/${event.id}/complete`);
                              toast.success('Follow-up completed!');
                              loadDashboardData();
                            } catch (error) { toast.error('Failed'); }
                          }}>Mark Complete</Button>
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
                <CardHeader><CardTitle>Grief Support Follow-ups</CardTitle></CardHeader>
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
                            <a href={formatPhoneForWhatsApp(stage.member_phone)} target="_blank" rel="noopener noreferrer">Contact</a>
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => markGriefStageComplete(stage.id)}>Mark Complete</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
            
            {hospitalFollowUp.length === 0 && griefDue.length === 0 && (
              <Card><CardContent className="p-6 text-center">No follow-ups needed today</CardContent></Card>
            )}
          </TabsContent>
          
          {/* Financial Aid Tab */}
          <TabsContent value="financial" className="space-y-4">
            <Card className="card-border-left-green">
              <CardHeader><CardTitle>Financial Aid Due Today</CardTitle></CardHeader>
              <CardContent>
                {financialAidDue.length === 0 ? (
                  <p className="text-center text-muted-foreground py-6">No financial aid scheduled for today</p>
                ) : (
                  <div className="space-y-2">
                    {financialAidDue.map(schedule => (
                      <div key={schedule.id} className="p-3 bg-green-50 rounded flex justify-between items-center">
                        <div className="flex-1">
                          <MemberNameWithAvatar member={{name: schedule.member_name, photo_url: schedule.member_photo_url}} memberId={schedule.member_id} />
                          <p className="text-sm text-muted-foreground ml-13">{schedule.frequency} - Rp {schedule.aid_amount?.toLocaleString('id-ID')} ({schedule.aid_type})</p>
                          <p className="text-xs ml-13">
                            <span className={schedule.days_overdue > 0 ? 'text-red-600 font-medium' : 'text-green-600'}>
                              {schedule.days_overdue > 0 ? `Overdue ${schedule.days_overdue} days` : 'Due today'} - Scheduled: {formatDate(schedule.next_occurrence)}
                            </span>
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" className="bg-green-500 hover:bg-green-600 text-white" asChild>
                            <a href={formatPhoneForWhatsApp(schedule.member_phone)} target="_blank" rel="noopener noreferrer">Contact</a>
                          </Button>
                          <Button size="sm" variant="outline" onClick={async () => {
                            if (window.confirm(`Mark aid as distributed to ${schedule.member_name}?`)) {
                              try {
                                await axios.post(`${API}/financial-aid-schedules/${schedule.id}/mark-distributed`);
                                toast.success('Payment distributed! Schedule advanced.');
                                loadDashboardData();
                              } catch (error) { toast.error('Failed'); }
                            }
                          }}>Mark Distributed</Button>
                          <Button size="sm" variant="ghost" className="text-red-600" onClick={async () => {
                            if (window.confirm(`Stop aid schedule for ${schedule.member_name}?`)) {
                              try {
                                await axios.post(`${API}/financial-aid-schedules/${schedule.id}/stop`);
                                toast.success('Schedule stopped');
                                loadDashboardData();
                              } catch (error) { toast.error('Failed'); }
                            }
                          }}>Stop</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          {/* Disconnected Tab */}
          <TabsContent value="disconnected" className="space-y-4">
            <Card className="card-border-left-red">
              <CardHeader><CardTitle>Members Disconnected ({engagementSettings.inactiveDays}+ days no contact)</CardTitle></CardHeader>
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
                            <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer">Contact</a>
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => markMemberContacted(member.id, member.name)}>Mark Contacted</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          {/* At-Risk Tab */}
          <TabsContent value="at-risk" className="space-y-4">
            <Card className="card-border-left-amber">
              <CardHeader><CardTitle>Members at Risk ({engagementSettings.atRiskDays}-{engagementSettings.inactiveDays-1} days no contact)</CardTitle></CardHeader>
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
                            <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer">Contact</a>
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => markMemberContacted(member.id, member.name)}>Mark Contacted</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          {/* Upcoming Tab */}
          <TabsContent value="upcoming" className="space-y-4">
            <Card className="card-border-left-purple">
              <CardHeader><CardTitle>Upcoming Birthdays (Next 7 Days)</CardTitle></CardHeader>
              <CardContent>
                {upcomingBirthdays.length === 0 ? (
                  <p className="text-center text-muted-foreground py-6">No birthdays coming up</p>
                ) : (
                  <div className="space-y-2">
                    {upcomingBirthdays.map(event => (
                      <div key={event.id} className="p-3 bg-purple-50 rounded flex justify-between items-center">
                        <div className="flex-1">
                          <MemberNameWithAvatar member={{name: event.member_name, photo_url: event.member_photo_url}} memberId={event.member_id} />
                          <p className="text-sm text-muted-foreground ml-13">{formatDate(event.event_date)}</p>
                        </div>
                        <span className="text-xs px-2 py-1 bg-purple-100 text-purple-600 rounded">
                          {Math.ceil((new Date(event.event_date) - new Date()) / (1000 * 60 * 60 * 24))} days
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
        {/* Recent Interactions */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl font-playfair">Recent Interactions</CardTitle>
            <p className="text-sm text-muted-foreground">Latest pastoral care activities</p>
          </CardHeader>
          <CardContent>
            {recentActivity.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No recent activities</p>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((event) => (
                  <div key={event.id} className="border-b pb-4 last:border-0">
                    <div className="flex justify-between items-start mb-1">
                      <p className="font-semibold text-sm uppercase tracking-wide">{event.event_type.replace('_', ' ')}</p>
                      <span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">By {user?.name}</p>
                    <p className="text-sm">{event.title}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Upcoming Reminders */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl font-playfair">Upcoming Reminders</CardTitle>
            <p className="text-sm text-muted-foreground">Tasks and follow-ups</p>
          </CardHeader>
          <CardContent>
            {upcomingEvents.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No upcoming reminders</p>
            ) : (
              <div className="space-y-4">
                {upcomingEvents.slice(0, 5).map((event) => (
                  <div key={event.id} className="border-b pb-4 last:border-0">
                    <div className="flex justify-between items-start mb-1">
                      <p className="font-semibold text-sm">{event.title}</p>
                      <span className="text-xs text-muted-foreground">{formatDate(event.event_date)}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{event.member_name}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;