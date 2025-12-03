import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PieChart, BarChart, AreaChart } from '@/components/charts';
import { TrendingUp, Users, DollarSign, Heart, Target } from 'lucide-react';

const COLORS = {
  primary: ['#14b8a6', '#f59e0b', '#ec4899', '#a78bfa', '#06b6d4', '#84cc16', '#f97316'],
  demographic: ['#14b8a6', '#f59e0b', '#ec4899', '#a78bfa', '#06b6d4', '#84cc16'],
  financial: ['#059669', '#f59e0b', '#14b8a6', '#a78bfa', '#0284c7']
};

export const Analytics = () => {
  const { t } = useTranslation();
  const [timeRange, setTimeRange] = useState('all');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [activeTab, setActiveTab] = useState('demographics');

  // Use TanStack Query for data fetching - leverages prefetched cache from route loader
  const { data, isLoading: loading, refetch } = useQuery({
    queryKey: ['analytics-dashboard', timeRange, customStartDate, customEndDate],
    queryFn: async () => {
      const params = new URLSearchParams({ time_range: timeRange });
      if (timeRange === 'custom' && customStartDate && customEndDate) {
        params.append('start_date', customStartDate);
        params.append('end_date', customEndDate);
      }
      const response = await api.get(`/analytics/dashboard?${params}`);
      return response.data;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  if (loading || !data) {
    return <div className="space-y-6 max-w-full"><Skeleton className="h-96 w-full" /></div>;
  }

  // Destructure pre-aggregated data from backend
  const { member_stats, demographics, events_by_type, events_by_month, financial, grief, trends } = data;

  return (
    <div className="space-y-6 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-3xl font-playfair font-bold text-foreground">{t('analytics')}</h1>
          <p className="text-muted-foreground mt-1">{t('pastoral_care_analytics')}</p>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('misc.all_time')}</SelectItem>
              <SelectItem value="year">{t('misc.this_year')}</SelectItem>
              <SelectItem value="6months">{t('misc.last_6_months')}</SelectItem>
              <SelectItem value="3months">{t('misc.last_3_months')}</SelectItem>
              <SelectItem value="custom">{t('misc.custom_date_range')}</SelectItem>
            </SelectContent>
          </Select>

          {timeRange === 'custom' && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="px-3 py-2 border rounded text-sm"
                placeholder={t('misc.start_date')}
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="px-3 py-2 border rounded text-sm"
                placeholder={t('misc.end_date')}
              />
              <Button
                size="sm"
                className="bg-teal-500 hover:bg-teal-600 text-white"
                onClick={() => refetch()}
                disabled={!customStartDate || !customEndDate}
              >
                {t('misc.apply')}
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
                <p className="text-3xl font-bold">{member_stats?.total || 0}</p>
                <p className="text-xs text-muted-foreground">{member_stats?.with_photos || 0} {t('with_photos')}</p>
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
                <p className="text-2xl font-bold">Rp {financial?.total_aid?.toLocaleString('id-ID') || 0}</p>
                <p className="text-xs text-muted-foreground">{financial?.schedules || 0} {t('active_schedules')}</p>
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
                <p className="text-3xl font-bold">{grief?.completion_rate || 0}%</p>
                <p className="text-xs text-muted-foreground">{t('completion_rate')}</p>
              </div>
              <Heart className="w-8 h-8 text-pink-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="card-border-left-purple">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t('avg_member_age')}</p>
                <p className="text-3xl font-bold">{member_stats?.avg_age || 0}</p>
                <p className="text-xs text-muted-foreground">{t('years_old')}</p>
              </div>
              <Target className="w-8 h-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="demographics" className="w-full" onValueChange={(v) => setActiveTab(v)}>
        <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex w-full">
            <TabsTrigger value="demographics" className="flex-shrink-0">
              <Users className="w-4 h-4" />
              {activeTab === 'demographics' && <span className="ml-2">{t('demographics')}</span>}
            </TabsTrigger>
            <TabsTrigger value="trends" className="flex-shrink-0">
              <TrendingUp className="w-4 h-4" />
              {activeTab === 'trends' && <span className="ml-2">{t('trends')}</span>}
            </TabsTrigger>
            <TabsTrigger value="engagement" className="flex-shrink-0">
              <TrendingUp className="w-4 h-4" />
              {activeTab === 'engagement' && <span className="ml-2">{t('engagement')}</span>}
            </TabsTrigger>
            <TabsTrigger value="financial" className="flex-shrink-0">
              <DollarSign className="w-4 h-4" />
              {activeTab === 'financial' && <span className="ml-2">{t('financial_aid')}</span>}
            </TabsTrigger>
            <TabsTrigger value="care" className="flex-shrink-0">
              <Heart className="w-4 h-4" />
              {activeTab === 'care' && <span className="ml-2">{t('care')}</span>}
            </TabsTrigger>
            <TabsTrigger value="predictive" className="flex-shrink-0">
              <Target className="w-4 h-4" />
              {activeTab === 'predictive' && <span className="ml-2">{t('predict')}</span>}
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Demographics Tab */}
        <TabsContent value="demographics" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>{t('age_distribution')}</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={demographics?.age_groups || []} color={COLORS.demographic[0]} height={300} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('membership_status')}</CardTitle></CardHeader>
              <CardContent>
                <PieChart data={demographics?.membership || []} colors={COLORS.demographic} height={300} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('gender_distribution')}</CardTitle></CardHeader>
              <CardContent>
                <PieChart data={demographics?.gender || []} colors={COLORS.primary} height={250} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('member_categories')}</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={demographics?.category || []} color={COLORS.primary[2]} height={250} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Demographic Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>{t('population_analysis_by_age')}</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={trends?.age_groups || []} color={COLORS.demographic[0]} height={300} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('engagement_by_membership')}</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={trends?.membership_trends || []} color={COLORS.primary[2]} height={300} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle>{t('ai_insights_recommendations')}</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded">
                    <p className="font-semibold text-blue-900 dark:text-blue-100">📊 {t('analytics_page.population_insights') || 'Population Insights'}</p>
                    <div className="mt-2 space-y-1">
                      {trends?.insights?.length > 0 ? (
                        trends.insights.slice(0, 3).map((insight, i) => (
                          <p key={i} className="text-sm text-blue-700 dark:text-blue-300">• {insight}</p>
                        ))
                      ) : (
                        <p className="text-sm text-blue-700 dark:text-blue-300">• {t('analytics_page.no_insights_available') || 'Collecting data for insights...'}</p>
                      )}
                    </div>
                  </div>
                  <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded">
                    <p className="font-semibold text-green-900 dark:text-green-100">💡 {t('analytics_page.care_adaptations') || 'Care Adaptations'}</p>
                    <div className="mt-2 space-y-1">
                      {trends?.care_adaptations?.length > 0 ? (
                        trends.care_adaptations.map((adaptation, i) => (
                          <p key={i} className="text-sm text-green-700 dark:text-green-300">• {adaptation}</p>
                        ))
                      ) : (
                        <p className="text-sm text-green-700 dark:text-green-300">• {t('analytics_page.no_adaptations_needed') || 'Continue current care programs'}</p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded">
                  <p className="font-semibold text-purple-900 dark:text-purple-100">🎯 {t('analytics_page.strategic_recommendations') || 'Strategic Recommendations'}</p>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm font-medium text-purple-700 dark:text-purple-300">{t('analytics_page.high_priority')}</p>
                      <p className="text-sm text-purple-600 dark:text-purple-400">{trends?.strategic_recommendations?.high || t('analytics_page.no_high_priority_actions')}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-purple-700 dark:text-purple-300">{t('analytics_page.medium_priority')}</p>
                      <p className="text-sm text-purple-600 dark:text-purple-400">{trends?.strategic_recommendations?.medium || t('analytics_page.engagement_levels_healthy')}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-purple-700 dark:text-purple-300">{t('analytics_page.long_term') || 'Long Term'}</p>
                      <p className="text-sm text-purple-600 dark:text-purple-400">{trends?.strategic_recommendations?.long || t('analytics_page.develop_ministry_approaches')}</p>
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
              <CardHeader><CardTitle>{t('member_engagement_status')}</CardTitle></CardHeader>
              <CardContent>
                <PieChart data={demographics?.engagement || []} colors={['#059669', '#f59e0b', '#ef4444']} height={300} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('care_events_by_month')} ({new Date().getFullYear()})</CardTitle></CardHeader>
              <CardContent>
                <AreaChart data={events_by_month || []} dataKey="events" color={COLORS.primary[0]} height={300} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Financial Analytics Tab */}
        <TabsContent value="financial" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>{t('financial_aid_by_type')}</CardTitle></CardHeader>
              <CardContent>
                <BarChart data={financial?.by_type || []} color={COLORS.financial[0]} height={300} formatValue={(value) => `Rp ${value.toLocaleString('id-ID')}`} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('aid_distribution_summary')}</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-4 bg-green-50 rounded">
                    <p className="text-2xl font-bold text-green-700">Rp {financial?.total_aid?.toLocaleString('id-ID') || 0}</p>
                    <p className="text-sm text-muted-foreground">{t('total_distributed')}</p>
                  </div>
                  <div className="text-center p-4 bg-blue-50 rounded">
                    <p className="text-2xl font-bold text-blue-700">Rp {financial?.scheduled_amount?.toLocaleString('id-ID') || 0}</p>
                    <p className="text-sm text-muted-foreground">{t('total_scheduled')}</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-semibold">{t('average_aid_by_type')}</h4>
                  {financial?.by_type?.map(type => (
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
            <CardHeader><CardTitle>{t('care_events_distribution')}</CardTitle></CardHeader>
            <CardContent>
              <PieChart data={events_by_type || []} colors={COLORS.primary} height={400} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Predictive Analytics Tab */}
        <TabsContent value="predictive" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>{t('member_care_insights')}</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="p-3 bg-red-50 rounded">
                    <p className="font-semibold text-red-700">{t('analytics_page.high_priority')} ({demographics?.engagement?.find(e => e.name === 'inactive')?.value || 0} {t('misc.members')})</p>
                    <p className="text-sm text-muted-foreground">{t('analytics_page.members_disconnected_attention')}</p>
                  </div>

                  <div className="p-3 bg-amber-50 rounded">
                    <p className="font-semibold text-amber-700">{t('analytics_page.medium_priority')} ({demographics?.engagement?.find(e => e.name === 'at_risk')?.value || 0} {t('misc.members')})</p>
                    <p className="text-sm text-muted-foreground">{t('analytics_page.at_risk_followup_needed')}</p>
                  </div>

                  <div className="p-3 bg-green-50 rounded">
                    <p className="font-semibold text-green-700">{t('analytics_page.active_members_count', {count: demographics?.engagement?.find(e => e.name === 'active')?.value || 0})}</p>
                    <p className="text-sm text-muted-foreground">{t('analytics_page.active_members_maintained')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>{t('financial_aid_effectiveness')}</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  {financial?.by_type?.slice(0, 4).map(type => (
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
