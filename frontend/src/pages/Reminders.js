import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Heart, Users, Hospital, Calendar, AlertTriangle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatDate = (dateStr) => {
  try {
    return new Date(dateStr).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
  } catch { return dateStr; }
};

export const Reminders = () => {
  const { user } = useAuth();
  const [birthdaysToday, setBirthdaysToday] = useState([]);
  const [griefDue, setGriefDue] = useState([]);
  const [hospitalFollowUp, setHospitalFollowUp] = useState([]);
  const [atRiskMembers, setAtRiskMembers] = useState([]);
  const [upcomingBirthdays, setUpcomingBirthdays] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadReminders();
  }, []);
  
  const loadReminders = async () => {
    try {
      const today = new Date().toISOString().split('T')[0];
      const weekAhead = new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0];
      
      const [eventsRes, griefRes, hospitalRes, atRiskRes] = await Promise.all([
        axios.get(`${API}/care-events`),
        axios.get(`${API}/grief-support?completed=false`),
        axios.get(`${API}/care-events/hospital/due-followup`),
        axios.get(`${API}/members/at-risk`)
      ]);
      
      // Filter birthdays for today
      const todayBirthdays = eventsRes.data.filter(e => 
        e.event_type === 'birthday' && e.event_date === today
      );
      
      // Get upcoming birthdays (next 7 days)
      const upcoming = eventsRes.data.filter(e => 
        e.event_type === 'birthday' && 
        e.event_date > today && 
        e.event_date <= weekAhead
      );
      
      // Filter grief stages due today
      const griefToday = griefRes.data.filter(g => g.scheduled_date === today);
      
      setBirthdaysToday(todayBirthdays);
      setUpcomingBirthdays(upcoming);
      setGriefDue(griefToday);
      setHospitalFollowUp(hospitalRes.data);
      setAtRiskMembers(atRiskRes.data.slice(0, 20));
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
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="today">
            <Calendar className="w-4 h-4 mr-2" />Today ({birthdaysToday.length + griefDue.length})
          </TabsTrigger>
          <TabsTrigger value="followup">
            <Hospital className="w-4 h-4 mr-2" />Follow-up ({hospitalFollowUp.length})
          </TabsTrigger>
          <TabsTrigger value="at-risk">
            <AlertTriangle className="w-4 h-4 mr-2" />At Risk ({atRiskMembers.length})
          </TabsTrigger>
          <TabsTrigger value="upcoming">
            <Heart className="w-4 h-4 mr-2" />Upcoming ({upcomingBirthdays.length})
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="today" className="space-y-4">
          {birthdaysToday.length === 0 && griefDue.length === 0 ? (
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
                          <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white">
                            Contact
                          </Button>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {griefDue.length > 0 && (
                <Card className="card-border-left-pink">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      💔 Grief Support Due ({griefDue.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {griefDue.map(stage => (
                        <div key={stage.id} className="p-3 bg-pink-50 rounded flex justify-between items-center">
                          <div>
                            <p className="font-semibold">{stage.member_name}</p>
                            <p className="text-sm text-muted-foreground">{stage.stage.replace('_', ' ')} stage</p>
                          </div>
                          <Button size="sm" className="bg-pink-500 hover:bg-pink-600 text-white">
                            Contact
                          </Button>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>
        
        <TabsContent value="followup" className="space-y-4">
          <Card className="card-border-left-blue">
            <CardHeader>
              <CardTitle>Hospital Follow-ups</CardTitle>
            </CardHeader>
            <CardContent>
              {hospitalFollowUp.length === 0 ? (
                <p className="text-center text-muted-foreground py-6">No hospital follow-ups due</p>
              ) : (
                <div className="space-y-2">
                  {hospitalFollowUp.map(event => (
                    <div key={event.id} className="p-3 bg-blue-50 rounded flex justify-between items-center">
                      <div>
                        <p className="font-semibold">{event.member_name}</p>
                        <p className="text-sm text-muted-foreground">{event.followup_reason}</p>
                      </div>
                      <Button size="sm" className="bg-blue-500 hover:bg-blue-600 text-white">
                        Contact
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
              <CardTitle>Members at Risk (30+ days no contact)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {atRiskMembers.map(member => (
                  <div key={member.id} className="p-3 bg-amber-50 rounded flex justify-between items-center">
                    <div>
                      <p className="font-semibold">{member.name}</p>
                      <p className="text-sm text-muted-foreground">{member.days_since_last_contact} days since contact</p>
                    </div>
                    <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white">
                      Contact
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
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