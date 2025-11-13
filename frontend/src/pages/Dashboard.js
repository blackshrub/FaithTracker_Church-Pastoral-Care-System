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
import { toast } from 'sonner';
import { Users, Heart, AlertTriangle, DollarSign, Plus, UserPlus, Bell, Calendar, Zap } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatDate = (dateStr) => {
  try {
    return new Date(dateStr).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return dateStr; }
};

export const Dashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [atRiskMembers, setAtRiskMembers] = useState([]);
  const [activeGrief, setActiveGrief] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
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
    // Financial aid scheduling
    schedule_frequency: 'one_time',
    schedule_start_date: new Date().toISOString().split('T')[0],
    schedule_end_date: '',
    day_of_week: 'monday',
    day_of_month: 1,
    month_of_year: 1
  });
  
  useEffect(() => {
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
      const [statsRes, atRiskRes, griefRes, recentRes, upcomingRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`),
        axios.get(`${API}/members/at-risk`),
        axios.get(`${API}/dashboard/grief-active`),
        axios.get(`${API}/dashboard/recent-activity?limit=8`),
        axios.get(`${API}/dashboard/upcoming?days=7`)
      ]);
      setStats(statsRes.data);
      setAtRiskMembers(atRiskRes.data.slice(0, 10));
      setActiveGrief(griefRes.data.slice(0, 5));
      setRecentActivity(recentRes.data);
      setUpcomingEvents(upcomingRes.data.slice(0, 8));
    } catch (error) {
      toast.error('Failed to load');
    } finally {
      setLoading(false);
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
                <div className="grid grid-cols-2 gap-4">
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
                  <div>
                    <Label>Date *</Label>
                    <Input type="date" value={quickEvent.event_date} onChange={(e) => setQuickEvent({...quickEvent, event_date: e.target.value})} required />
                  </div>
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
      
      {/* Two Column Layout - Priority Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* At-Risk Members Widget */}
        <Card className="card-border-left-amber shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl font-playfair flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              Members at Risk ({stats?.members_at_risk || 0})
            </CardTitle>
            <p className="text-sm text-muted-foreground">30+ days since last contact</p>
          </CardHeader>
          <CardContent>
            {atRiskMembers.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">All members recently contacted!</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {atRiskMembers.map((member) => (
                  <div key={member.id} className="flex items-center justify-between p-3 bg-amber-50 rounded-lg hover:bg-amber-100 transition-colors">
                    <div className="flex-1">
                      <p className="font-semibold">{member.name}</p>
                      <p className="text-sm text-muted-foreground">{member.phone}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-semibold text-amber-700">{member.days_since_last_contact} days</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Active Grief Support Widget */}
        <Card className="card-border-left-pink shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl font-playfair flex items-center gap-2">
              <Heart className="w-5 h-5 text-pink-600" />
              Active Grief Support ({stats?.active_grief_support || 0})
            </CardTitle>
            <p className="text-sm text-muted-foreground">Members in grief care timeline</p>
          </CardHeader>
          <CardContent>
            {activeGrief.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No active grief support</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {activeGrief.map((grief) => (
                  <div key={grief.member_id} className="p-3 bg-pink-50 rounded-lg hover:bg-pink-100 transition-colors">
                    <p className="font-semibold">{grief.member_name}</p>
                    <p className="text-sm text-muted-foreground">{grief.stages.length} stages pending</p>
                    <Link to={`/members/${grief.member_id}`}>
                      <Button size="sm" variant="outline" className="mt-2">View Timeline</Button>
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      
      {/* Two Column Layout - Recent & Upcoming */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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