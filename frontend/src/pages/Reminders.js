import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Heart, Users, Hospital, Calendar, AlertTriangle } from 'lucide-react';

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

const markMemberContacted = async (memberId, memberName) => {
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

export const Reminders = () => {
  const { user } = useAuth();
  const [birthdaysToday, setBirthdaysToday] = useState([]);
  const [griefDue, setGriefDue] = useState([]);
  const [griefToday, setGriefToday] = useState([]);
  const [hospitalFollowUp, setHospitalFollowUp] = useState([]);
  const [atRiskMembers, setAtRiskMembers] = useState([]);
  const [disconnectedMembers, setDisconnectedMembers] = useState([]);
  const [upcomingBirthdays, setUpcomingBirthdays] = useState([]);
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
      
      const [eventsRes, griefRes, hospitalRes, atRiskRes, membersRes] = await Promise.all([
        axios.get(`${API}/care-events`),
        axios.get(`${API}/grief-support?completed=false`),
        axios.get(`${API}/care-events/hospital/due-followup`),
        axios.get(`${API}/members/at-risk`),
        axios.get(`${API}/members`)
      ]);
      
      // Get member names and phones for events
      const memberMap = {};
      membersRes.data.forEach(m => memberMap[m.id] = { name: m.name, phone: m.phone });
      
      // Filter birthdays for today with member names
      const todayBirthdays = eventsRes.data.filter(e => 
        e.event_type === 'birthday' && e.event_date === today
      ).map(e => ({...e, member_name: memberMap[e.member_id]?.name, member_phone: memberMap[e.member_id]?.phone}));
      
      // Get upcoming birthdays with member names
      const upcoming = eventsRes.data.filter(e => 
        e.event_type === 'birthday' && 
        e.event_date > today && 
        e.event_date <= weekAhead
      ).map(e => ({...e, member_name: memberMap[e.member_id]?.name, member_phone: memberMap[e.member_id]?.phone}));
      
      // Filter grief stages due today AND overdue (for follow-up tab)
      const griefToday = griefRes.data.filter(g => g.scheduled_date === today).map(g => ({
        ...g,
        member_name: memberMap[g.member_id]?.name,
        member_phone: memberMap[g.member_id]?.phone
      }));
      
      // Filter overdue grief stages for follow-up tab
      const griefOverdue = griefRes.data.filter(g => {
        const schedDate = new Date(g.scheduled_date);
        return schedDate <= new Date() && !g.completed;
      }).map(g => ({
        ...g,
        member_name: memberMap[g.member_id]?.name,
        member_phone: memberMap[g.member_id]?.phone
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
      setHospitalFollowUp(hospitalRes.data.map(h => ({...h, member_name: memberMap[h.member_id]?.name, member_phone: memberMap[h.member_id]?.phone})));
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
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-playfair font-bold">Pastoral Care Reminders</h1>
        <p className="text-muted-foreground mt-1">{totalTasks} tasks need your attention today</p>
      </div>
      
      <Tabs defaultValue="today" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="today">
            <Calendar className="w-4 h-4 mr-2" />Today ({birthdaysToday.length + griefToday.length})
          </TabsTrigger>
          <TabsTrigger value="followup">
            <Hospital className="w-4 h-4 mr-2" />Follow-up ({hospitalFollowUp.length + griefDue.length})
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
                          <div>
                            <p className="font-semibold">{event.member_name}</p>
                            <p className="text-sm text-muted-foreground">Call to wish happy birthday</p>
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
                          <div>
                            <p className="font-semibold">{stage.member_name}</p>
                            <p className="text-sm text-muted-foreground">{stage.stage.replace('_', ' ')} stage</p>
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
                      <div>
                        <p className="font-semibold">{member.name}</p>
                        <p className="text-sm text-muted-foreground">{member.days_since_last_contact} days since contact</p>
                      </div>
                      <Button size="sm" className="bg-red-500 hover:bg-red-600 text-white" asChild>
                        <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer">
                          Reconnect
                        </a>
                      </Button>
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
                      <div>
                        <p className="font-semibold">{member.name}</p>
                        <p className="text-sm text-muted-foreground">{member.days_since_last_contact} days since contact</p>
                      </div>
                      <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" asChild>
                        <a href={formatPhoneForWhatsApp(member.phone)} target="_blank" rel="noopener noreferrer">
                          Contact
                        </a>
                      </Button>
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
                      <div>
                        <p className="font-semibold">{event.member_name}</p>
                        <p className="text-sm text-muted-foreground">{event.followup_reason}</p>
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
                      <div>
                        <p className="font-semibold">{stage.member_name}</p>
                        <p className="text-sm text-muted-foreground">{stage.stage.replace('_', ' ')} after mourning</p>
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
                      <div>
                        <p className="font-semibold">{event.member_name}</p>
                        <p className="text-sm text-muted-foreground">{formatDate(event.event_date)}</p>
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

export default Reminders;