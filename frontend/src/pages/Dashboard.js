import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Heart, Users, Hospital, Calendar, AlertTriangle, DollarSign } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatDate = (dateStr) => {
  try {
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
  const { user } = useAuth();
  const [birthdaysToday, setBirthdaysToday] = useState([]);
  const [griefDue, setGriefDue] = useState([]);
  const [griefToday, setGriefToday] = useState([]);
  const [hospitalFollowUp, setHospitalFollowUp] = useState([]);
  const [atRiskMembers, setAtRiskMembers] = useState([]);
  const [disconnectedMembers, setDisconnectedMembers] = useState([]);
  const [upcomingBirthdays, setUpcomingBirthdays] = useState([]);
  const [financialAidDue, setFinancialAidDue] = useState([]);
  const [loading, setLoading] = useState(true);
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
      const today = new Date().toISOString().split('T')[0];
      const weekAhead = new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0];
      
      const [eventsRes, griefRes, hospitalRes, atRiskRes, membersRes, aidDueRes] = await Promise.all([
        axios.get(`${API}/care-events`),
        axios.get(`${API}/grief-support?completed=false`),
        axios.get(`${API}/care-events/hospital/due-followup`),
        axios.get(`${API}/members/at-risk`),
        axios.get(`${API}/members`),
        axios.get(`${API}/financial-aid-schedules/due-today`)
      ]);
      
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
      setGriefToday(griefToday);  // Set grief stages due today
      setGriefDue(griefOverdue);  // Use overdue for follow-up tab
      setHospitalFollowUp(hospitalRes.data.map(h => ({...h, member_name: memberMap[h.member_id]?.name, member_phone: memberMap[h.member_id]?.phone, member_photo_url: memberMap[h.member_id]?.photo_url})));
      setFinancialAidDue(aidDueRes.data);
      setAtRiskMembers(atRisk);
      setDisconnectedMembers(disconnected);
    } catch (error) {
      console.error('Error loading reminders');
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <div>Loading...</div>;
  
  const totalTasks = birthdaysToday.length + griefDue.length + hospitalFollowUp.length + Math.min(atRiskMembers.length, 10);
  
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
                <p className="text-sm text-muted-foreground mb-1">Total Interactions</p>
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
                <p className="text-sm text-muted-foreground mb-1">Pending Reminders</p>
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
                <p className="text-sm text-muted-foreground mb-1">At Risk + Disconnected</p>
                <p className="text-4xl font-playfair font-bold">{atRiskMembers.length + disconnectedMembers.length}</p>
              </div>
              <div className="w-14 h-14 rounded-full bg-purple-100 flex items-center justify-center">
                <Heart className="w-7 h-7 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Task Management */}
      <div>
        <h1 className="text-3xl font-playfair font-bold">Today's Tasks & Reminders</h1>
        <p className="text-muted-foreground mt-1">{birthdaysToday.length + griefToday.length + financialAidDue.length + atRiskMembers.length + disconnectedMembers.length} tasks need your attention</p>
      </div>
      
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
                            <Button size="sm" variant="outline" onClick={() => markBirthdayComplete(event.id, loadReminders)}>
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
        
        <TabsContent value="followup" className="space-y-4">
          {/* Accident/Illness Follow-ups */}
          {hospitalFollowUp.length > 0 && (
            <Card className="card-border-left-blue">
              <CardHeader>
                <CardTitle>Accident/Illness Follow-ups</CardTitle>
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
          
          {hospitalFollowUp.length === 0 && griefDue.length === 0 && (
            <Card><CardContent className="p-6 text-center">No follow-ups needed today</CardContent></Card>
          )}
        </TabsContent>
        
        <TabsContent value="upcoming" className="space-y-4">
          <Card className="card-border-left-purple">
            <CardHeader>
              <CardTitle>Upcoming Birthdays (Next 7 Days)</CardTitle>
            </CardHeader>
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
                      <Badge variant="outline" className="text-purple-600">
                        {Math.ceil((new Date(event.event_date) - new Date()) / (1000 * 60 * 60 * 24))} days
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Dashboard;