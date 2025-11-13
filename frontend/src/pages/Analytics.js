import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = [
  'hsl(45, 90%, 65%)',
  'hsl(330, 75%, 70%)',
  'hsl(240, 15%, 45%)',
  'hsl(25, 85%, 62%)',
  'hsl(15, 70%, 58%)',
  'hsl(200, 40%, 50%)',
  'hsl(140, 55%, 48%)',
  'hsl(180, 42%, 45%)'
];

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend, LineChart, Line, Area, AreaChart } from 'recharts';
import { TrendingUp, Users, DollarSign, Heart, Calendar, Target } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = {
  primary: ['#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'],
  demographic: ['#0ea5e9', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16'],
  financial: ['#059669', '#dc2626', '#d97706', '#7c3aed', '#0284c7']
};

export const Analytics = () => {
  const { t } = useTranslation();
  const [memberStats, setMemberStats] = useState(null);
  const [eventsByType, setEventsByType] = useState([]);
  const [demographicData, setDemographicData] = useState({});
  const [financialData, setFinancialData] = useState({});
  const [engagementData, setEngagementData] = useState({});
  const [griefData, setGriefData] = useState({});
  const [timeRange, setTimeRange] = useState('all');
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadAnalytics();
  }, [timeRange]);
  
  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const [membersRes, eventsRes, griefRes, aidSummaryRes, scheduleRes] = await Promise.all([
        axios.get(`${API}/members`),
        axios.get(`${API}/care-events`),
        axios.get(`${API}/analytics/grief-completion-rate`),
        axios.get(`${API}/financial-aid/summary`),
        axios.get(`${API}/financial-aid-schedules`)
      ]);
      
      const members = membersRes.data;
      const events = eventsRes.data;
      
      // Member Demographics
      const ageGroups = { 'Child (0-12)': 0, 'Teen (13-17)': 0, 'Youth (18-30)': 0, 'Adult (31-60)': 0, 'Senior (60+)': 0 };
      const genderData = { Male: 0, Female: 0, Unknown: 0 };
      const membershipData = { Member: 0, 'Non Member': 0, Visitor: 0, Sympathizer: 0, 'Inactive': 0 };
      const categoryData = { Umum: 0, Youth: 0, Teen: 0, Usinda: 0, Other: 0 };
      const engagementStatus = { active: 0, at_risk: 0, inactive: 0 };
      
      members.forEach(m => {
        // Age groups
        const age = m.age || 0;
        if (age <= 12) ageGroups['Child (0-12)']++;
        else if (age <= 17) ageGroups['Teen (13-17)']++;
        else if (age <= 30) ageGroups['Youth (18-30)']++;
        else if (age <= 60) ageGroups['Adult (31-60)']++;
        else ageGroups['Senior (60+)']++;
        
        // Gender
        if (m.gender === 'M') genderData.Male++;
        else if (m.gender === 'F') genderData.Female++;
        else genderData.Unknown++;
        
        // Membership
        const membership = m.membership_status || 'Unknown';
        if (membershipData.hasOwnProperty(membership)) membershipData[membership]++;
        
        // Category
        const category = m.category || 'Other';
        if (categoryData.hasOwnProperty(category)) categoryData[category]++;
        else categoryData.Other++;
        
        // Engagement
        const status = m.engagement_status || 'inactive';
        engagementStatus[status]++;
      });
      
      // Care Event Analysis
      const eventTypeCount = {};
      const eventsByMonth = {};
      const currentYear = new Date().getFullYear();
      
      events.forEach(e => {
        // Event types
        eventTypeCount[e.event_type] = (eventTypeCount[e.event_type] || 0) + 1;
        
        // Events by month
        const date = new Date(e.event_date);
        if (date.getFullYear() === currentYear) {
          const month = date.toLocaleDateString('en', { month: 'short' });
          eventsByMonth[month] = (eventsByMonth[month] || 0) + 1;
        }
      });
      
      // Financial Analysis
      const financialByType = aidSummaryRes.data.by_type || {};
      const totalFinancialAid = aidSummaryRes.data.total_amount || 0;
      const avgAidByType = {};
      Object.entries(financialByType).forEach(([type, data]) => {
        avgAidByType[type] = data.count > 0 ? Math.round(data.total_amount / data.count) : 0;
      });
      
      // Set all data
      setMemberStats({
        total: members.length,
        withPhotos: members.filter(m => m.photo_url).length,
        avgAge: Math.round(members.reduce((sum, m) => sum + (m.age || 0), 0) / members.length)
      });
      
      setEventsByType(Object.entries(eventTypeCount).map(([type, count]) => ({ 
        name: type.replace('_', ' ').toUpperCase(), 
        value: count,
        percentage: Math.round(count / events.length * 100)
      })));
      
      setDemographicData({
        ageGroups: Object.entries(ageGroups).map(([group, count]) => ({ name: group, value: count })),
        gender: Object.entries(genderData).map(([gender, count]) => ({ name: gender, value: count })),
        membership: Object.entries(membershipData).map(([status, count]) => ({ name: status, value: count })),
        category: Object.entries(categoryData).map(([cat, count]) => ({ name: cat, value: count })),
        engagement: Object.entries(engagementStatus).map(([status, count]) => ({ name: status, value: count }))
      });
      
      setFinancialData({
        totalAid: totalFinancialAid,
        byType: Object.entries(financialByType).map(([type, data]) => ({ 
          name: type.replace('_', ' '),
          amount: data.total_amount,
          count: data.count,
          avg: avgAidByType[type]
        })),
        schedules: scheduleRes.data.length,
        scheduledAmount: scheduleRes.data.reduce((sum, s) => sum + (s.aid_amount || 0), 0)
      });
      
      setEngagementData({
        trends: Object.entries(eventsByMonth).map(([month, count]) => ({ month, events: count }))
      });
      
      setGriefData(griefRes.data);
      
    } catch (error) {
      console.error('Error loading analytics:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return <div className="space-y-6"><Skeleton className="h-96 w-full" /></div>;
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-playfair font-bold text-foreground">Advanced Analytics</h1>
          <p className="text-muted-foreground mt-1">Comprehensive pastoral care insights and trends</p>
        </div>
        <Select value={timeRange} onValueChange={setTimeRange}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Time</SelectItem>
            <SelectItem value="year">This Year</SelectItem>
            <SelectItem value="6months">Last 6 Months</SelectItem>
            <SelectItem value="3months">Last 3 Months</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="card-border-left-teal">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Members</p>
                <p className="text-3xl font-bold">{memberStats?.total || 0}</p>
                <p className="text-xs text-muted-foreground">{memberStats?.withPhotos || 0} with photos</p>
              </div>
              <Users className="w-8 h-8 text-teal-600" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-amber">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Financial Aid</p>
                <p className="text-2xl font-bold">Rp {financialData?.totalAid?.toLocaleString('id-ID') || 0}</p>
                <p className="text-xs text-muted-foreground">{financialData?.schedules || 0} active schedules</p>
              </div>
              <DollarSign className="w-8 h-8 text-amber-600" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-pink">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Grief Support</p>
                <p className="text-3xl font-bold">{griefData?.completion_rate || 0}%</p>
                <p className="text-xs text-muted-foreground">completion rate</p>
              </div>
              <Heart className="w-8 h-8 text-pink-600" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="card-border-left-purple">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Avg Member Age</p>
                <p className="text-3xl font-bold">{memberStats?.avgAge || 0}</p>
                <p className="text-xs text-muted-foreground">years old</p>
              </div>
              <Target className="w-8 h-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>
      
      <Tabs defaultValue="demographics" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="demographics"><Users className="w-4 h-4 mr-2" />Demographics</TabsTrigger>
          <TabsTrigger value="engagement"><TrendingUp className="w-4 h-4 mr-2" />Engagement</TabsTrigger>
          <TabsTrigger value="financial"><DollarSign className="w-4 h-4 mr-2" />Financial</TabsTrigger>
          <TabsTrigger value="care"><Heart className="w-4 h-4 mr-2" />Care Events</TabsTrigger>
          <TabsTrigger value="predictive"><Target className="w-4 h-4 mr-2" />Predictive</TabsTrigger>
        </TabsList>
        
        {/* Demographics Tab */}
        <TabsContent value="demographics" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Age Distribution</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={demographicData.ageGroups}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill={COLORS.demographic[0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Membership Status</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={demographicData.membership} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}>
                      {demographicData.membership?.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS.demographic[index % COLORS.demographic.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Gender Distribution</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={demographicData.gender} cx="50%" cy="50%" outerRadius={60} dataKey="value">
                      {demographicData.gender?.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS.primary[index]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Member Categories</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={demographicData.category}>
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill={COLORS.primary[2]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        {/* Engagement Tab */}
        <TabsContent value="engagement" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Member Engagement Status</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={demographicData.engagement} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({name, value}) => `${name}: ${value}`}>
                      <Cell fill="#059669" /> {/* Active - Green */}
                      <Cell fill="#f59e0b" /> {/* At Risk - Amber */}
                      <Cell fill="#ef4444" /> {/* Inactive - Red */}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Care Events by Month ({new Date().getFullYear()})</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={engagementData.trends}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Area type="monotone" dataKey="events" stroke={COLORS.primary[0]} fill={COLORS.primary[0]} fillOpacity={0.3} />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        {/* Financial Analytics Tab */}
        <TabsContent value="financial" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Financial Aid by Type</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={financialData.byType}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value) => `Rp ${value.toLocaleString('id-ID')}`} />
                    <Bar dataKey="amount" fill={COLORS.financial[0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Aid Distribution Summary</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-4 bg-green-50 rounded">
                    <p className="text-2xl font-bold text-green-700">Rp {financialData?.totalAid?.toLocaleString('id-ID') || 0}</p>
                    <p className="text-sm text-muted-foreground">Total Distributed</p>
                  </div>
                  <div className="text-center p-4 bg-blue-50 rounded">
                    <p className="text-2xl font-bold text-blue-700">Rp {financialData?.scheduledAmount?.toLocaleString('id-ID') || 0}</p>
                    <p className="text-sm text-muted-foreground">Total Scheduled</p>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <h4 className="font-semibold">Average Aid by Type</h4>
                  {financialData.byType?.map(type => (
                    <div key={type.name} className="flex justify-between items-center p-2 bg-muted/30 rounded">
                      <span className="text-sm">{type.name}</span>
                      <span className="font-semibold">Rp {type.avg?.toLocaleString('id-ID')}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        {/* Care Events Tab */}
        <TabsContent value="care" className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Care Events Distribution</CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <PieChart>
                  <Pie data={eventsByType} cx="50%" cy="50%" outerRadius={120} dataKey="value" label={({name, percentage}) => `${name}: ${percentage}%`}>
                    {eventsByType.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS.primary[index % COLORS.primary.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Predictive Analytics Tab */}
        <TabsContent value="predictive" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Member Care Insights</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="p-3 bg-red-50 rounded">
                    <p className="font-semibold text-red-700">High Priority ({demographicData.engagement?.find(e => e.name === 'inactive')?.value || 0} members)</p>
                    <p className="text-sm text-muted-foreground">Members disconnected - need immediate attention</p>
                  </div>
                  
                  <div className="p-3 bg-amber-50 rounded">
                    <p className="font-semibold text-amber-700">Medium Priority ({demographicData.engagement?.find(e => e.name === 'at_risk')?.value || 0} members)</p>
                    <p className="text-sm text-muted-foreground">At-risk members - follow up needed</p>
                  </div>
                  
                  <div className="p-3 bg-green-50 rounded">
                    <p className="font-semibold text-green-700">Active Members ({demographicData.engagement?.find(e => e.name === 'active')?.value || 0} members)</p>
                    <p className="text-sm text-muted-foreground">Regular contact maintained</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Financial Aid Effectiveness</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  {financialData.byType?.slice(0, 4).map(type => (
                    <div key={type.name} className="flex items-center justify-between p-3 bg-green-50 rounded">
                      <div>
                        <p className="font-semibold text-green-700">{type.name}</p>
                        <p className="text-sm text-muted-foreground">{type.count} recipients</p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-green-700">Rp {type.amount?.toLocaleString('id-ID')}</p>
                        <p className="text-xs text-muted-foreground">avg: Rp {type.avg?.toLocaleString('id-ID')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Analytics;