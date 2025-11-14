import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PieChart, BarChart, AreaChart } from '@/components/charts';
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
  const [trendsData, setTrendsData] = useState({});
  const [timeRange, setTimeRange] = useState('all');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadAnalytics();
  }, [timeRange]);
  
  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const [membersRes, eventsRes, griefRes, aidSummaryRes, scheduleRes] = await Promise.all([
        axios.get(`${API}/members?limit=1000`), // Get all members for analytics
        axios.get(`${API}/care-events`),
        axios.get(`${API}/analytics/grief-completion-rate`),
        axios.get(`${API}/financial-aid/summary`),
        axios.get(`${API}/financial-aid-schedules`)
      ]);
      
      const members = membersRes.data;
      let events = eventsRes.data;
      
      // Apply date filtering based on timeRange
      if (timeRange !== 'all') {
        const now = new Date();
        let cutoffDate;
        
        if (timeRange === 'year') {
          cutoffDate = new Date(now.getFullYear(), 0, 1);
        } else if (timeRange === '6months') {
          cutoffDate = new Date(now.setMonth(now.getMonth() - 6));
        } else if (timeRange === '3months') {
          cutoffDate = new Date(now.setMonth(now.getMonth() - 3));
        } else if (timeRange === 'custom' && customStartDate && customEndDate) {
          events = events.filter(e => {
            const eventDate = new Date(e.event_date);
            return eventDate >= new Date(customStartDate) && eventDate <= new Date(customEndDate);
          });
        }
        
        if (timeRange !== 'custom') {
          events = events.filter(e => new Date(e.event_date) >= cutoffDate);
        }
      }
      
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
      
      // Care Event Analysis (excluding birthdays for relevant insights)
      const eventTypeCount = {};
      const eventsByMonth = {};
      const currentYear = new Date().getFullYear();
      
      events.forEach(e => {
        // Event types (exclude birthday for meaningful analysis)
        if (e.event_type !== 'birthday') {
          eventTypeCount[e.event_type] = (eventTypeCount[e.event_type] || 0) + 1;
        }
        
        // Events by month (all events including birthdays)
        const date = new Date(e.event_date);
        if (date.getFullYear() === currentYear) {
          const month = date.toLocaleDateString('en', { month: 'short' });
          eventsByMonth[month] = (eventsByMonth[month] || 0) + 1;
        }
      });
      
      // Calculate total non-birthday events for percentages
      const totalNonBirthdayEvents = Object.values(eventTypeCount).reduce((sum, count) => sum + count, 0);
      
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
        percentage: totalNonBirthdayEvents > 0 ? Math.round(count / totalNonBirthdayEvents * 100) : 0
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
          <h1 className="text-3xl font-playfair font-bold text-foreground">{t('analytics')}</h1>
          <p className="text-muted-foreground mt-1">{t('pastoral_care_analytics')}</p>
        </div>
        <div className="flex items-center gap-4">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Time</SelectItem>
              <SelectItem value="year">This Year</SelectItem>
              <SelectItem value="6months">Last 6 Months</SelectItem>
              <SelectItem value="3months">Last 3 Months</SelectItem>
              <SelectItem value="custom">Custom Date Range</SelectItem>
            </SelectContent>
          </Select>
          
          {timeRange === 'custom' && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="px-3 py-2 border rounded text-sm"
                placeholder="Start date"
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="px-3 py-2 border rounded text-sm"
                placeholder="End date"
              />
              <Button 
                size="sm" 
                className="bg-teal-500 hover:bg-teal-600 text-white"
                onClick={() => loadAnalytics()}
                disabled={!customStartDate || !customEndDate}
              >
                Apply
              </Button>
            </div>
          )}
        </div>
      </div>
      
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="card-border-left-teal">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t('total_members')}</p>
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
                <p className="text-sm text-muted-foreground">{t('total_aid')}</p>
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
                <p className="text-sm text-muted-foreground">{t('grief_support')}</p>
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
        <div className="overflow-x-auto">
          <TabsList className="inline-flex w-max min-w-full">
            <TabsTrigger value="demographics" className="whitespace-nowrap text-xs"><Users className="w-3 h-3 mr-1" />Demo</TabsTrigger>
            <TabsTrigger value="trends" className="whitespace-nowrap text-xs"><TrendingUp className="w-3 h-3 mr-1" />Trends</TabsTrigger>
            <TabsTrigger value="engagement" className="whitespace-nowrap text-xs"><TrendingUp className="w-3 h-3 mr-1" />Engage</TabsTrigger>
            <TabsTrigger value="financial" className="whitespace-nowrap text-xs"><DollarSign className="w-3 h-3 mr-1" />Financial</TabsTrigger>
            <TabsTrigger value="care" className="whitespace-nowrap text-xs"><Heart className="w-3 h-3 mr-1" />Care</TabsTrigger>
            <TabsTrigger value="predictive" className="whitespace-nowrap text-xs"><Target className="w-3 h-3 mr-1" />Predict</TabsTrigger>
          </TabsList>
        </div>
        
        {/* Demographics Tab */}
        <TabsContent value="demographics" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>{t('age_distribution')}</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={demographicData.ageGroups || []} color={COLORS.demographic[0]} height={300} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>{t('membership_status')}</CardTitle></CardHeader>
              <CardContent>
                <PieChart data={demographicData.membership || []} colors={COLORS.demographic} height={300} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>{t('gender_distribution')}</CardTitle></CardHeader>
              <CardContent>
                <PieChart data={demographicData.gender || []} colors={COLORS.primary} height={250} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Member Categories</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={demographicData.category || []} color={COLORS.primary[2]} height={250} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        {/* Demographic Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Population Analysis by Age Group</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={trendsData.age_groups || []} color={COLORS.demographic[0]} height={300} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Engagement by Membership Status</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={trendsData.membership_trends || []} color={COLORS.primary[2]} height={300} />
              </CardContent>
            </Card>
          </div>
          
          <Card>
            <CardHeader><CardTitle>AI Insights & Recommendations</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-blue-50 rounded">
                    <p className="font-semibold text-blue-900">📊 Population Insights</p>
                    <div className="mt-2 space-y-1">
                      {trendsData.insights?.slice(0, 3).map((insight, i) => (
                        <p key={i} className="text-sm text-blue-700">• {insight}</p>
                      ))}
                    </div>
                  </div>
                  <div className="p-4 bg-green-50 rounded">
                    <p className="font-semibold text-green-900">💡 Care Adaptations</p>
                    <div className="mt-2 space-y-1">
                      <p className="text-sm text-green-700">• Focus senior care programs for 60+ age group</p>
                      <p className="text-sm text-green-700">• Increase visitor engagement initiatives</p>
                      <p className="text-sm text-green-700">• Develop young adult retention strategies</p>
                    </div>
                  </div>
                </div>
                
                <div className="p-4 bg-purple-50 rounded">
                  <p className="font-semibold text-purple-900">🎯 Strategic Recommendations</p>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm font-medium text-purple-700">High Priority</p>
                      <p className="text-sm text-purple-600">Members with 90+ days no contact need immediate attention</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-purple-700">Medium Priority</p>
                      <p className="text-sm text-purple-600">Seniors and visitors require specialized care programs</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-purple-700">Long Term</p>
                      <p className="text-sm text-purple-600">Develop demographic-specific ministry approaches</p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Engagement Tab */}
        <TabsContent value="engagement" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Member Engagement Status</CardTitle></CardHeader>
              <CardContent>
                <PieChart data={demographicData.engagement || []} colors={['#059669', '#f59e0b', '#ef4444']} height={300} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Care Events by Month ({new Date().getFullYear()})</CardTitle></CardHeader>
              <CardContent>
                <AreaChart data={engagementData.trends || []} dataKey="events" color={COLORS.primary[0]} height={300} />
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
                <BarChart data={financialData.byType || []} color={COLORS.financial[0]} height={300} formatValue={(value) => `Rp ${value.toLocaleString('id-ID')}`} />
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
              <PieChart data={eventsByType} colors={COLORS.primary} height={400} />
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