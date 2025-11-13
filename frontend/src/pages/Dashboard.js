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
    aid_amount: ''
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
        await axios.post(`${API}/care-events`, {
          member_id: memberId,
          campus_id: 'auto',
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
        aid_amount: ''
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Link to="/members">
            <Button className="w-full h-14 bg-teal-500 hover:bg-teal-600 text-white text-base font-semibold">
              <Plus className="w-5 h-5 mr-2" />Add New Member
            </Button>
          </Link>
          <Link to="/members">
            <Button className="w-full h-14 bg-amber-500 hover:bg-amber-600 text-white text-base font-semibold">
              <Users className="w-5 h-5 mr-2" />View All Members
            </Button>
          </Link>
          <Dialog open={quickEventOpen} onOpenChange={setQuickEventOpen}>
            <DialogTrigger asChild>
              <Button className="w-full h-14 bg-pink-500 hover:bg-pink-600 text-white text-base font-semibold">
                <Zap className="w-5 h-5 mr-2" />Quick Care Event
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Quick Care Event (Multi-Member)</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleQuickEvent} className="space-y-4">
                <div className="space-y-2">
                  <Label>Search and Select Members *</Label>
                  <Input
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder="Type to search members..."
                  />
                  <div className="max-h-48 overflow-y-auto border rounded p-2 space-y-1">
                    {filteredMembers.slice(0, 20).map(member => (
                      <div key={member.id} className="flex items-center gap-2">
                        <Checkbox
                          checked={selectedMemberIds.includes(member.id)}
                          onCheckedChange={() => toggleMemberSelection(member.id)}
                        />
                        <span className="text-sm">{member.name} ({member.phone})</span>
                      </div>
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground">{selectedMemberIds.length} members selected</p>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Event Type *</Label>
                    <Select value={quickEvent.event_type} onValueChange={(v) => setQuickEvent({...quickEvent, event_type: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="birthday">🎂 Birthday</SelectItem>
                        <SelectItem value="financial_aid">💰 Financial Aid</SelectItem>
                        <SelectItem value="grief_loss">💔 Grief/Loss</SelectItem>
                        <SelectItem value="hospital_visit">🏥 Hospital Visit</SelectItem>
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
                  <Input value={quickEvent.title} onChange={(e) => setQuickEvent({...quickEvent, title: e.target.value})} placeholder="e.g., Financial assistance" required />
                </div>
                
                {quickEvent.event_type === 'financial_aid' && (
                  <div className="grid grid-cols-2 gap-4 p-4 bg-green-50 rounded">
                    <div>
                      <Label>Aid Type *</Label>
                      <Select value={quickEvent.aid_type} onValueChange={(v) => setQuickEvent({...quickEvent, aid_type: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="education">Education</SelectItem>
                          <SelectItem value="medical">Medical</SelectItem>
                          <SelectItem value="emergency">Emergency</SelectItem>
                          <SelectItem value="housing">Housing</SelectItem>
                          <SelectItem value="food">Food</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Amount (Rp) *</Label>
                      <Input type="number" value={quickEvent.aid_amount} onChange={(e) => setQuickEvent({...quickEvent, aid_amount: e.target.value})} required />
                    </div>
                  </div>
                )}
                
                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="outline" onClick={() => setQuickEventOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-teal-500 hover:bg-teal-600 text-white">Save for {selectedMemberIds.length} Members</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
          <Link to="/members">
            <Button className="w-full h-14 bg-purple-500 hover:bg-purple-600 text-white text-base font-semibold">
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