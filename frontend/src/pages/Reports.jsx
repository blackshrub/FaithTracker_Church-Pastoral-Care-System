import React, { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { BarChart, PieChart, AreaChart } from '@/components/charts';
import {
  FileText, Users, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2,
  Calendar, DollarSign, Heart, Gift, Activity, Download, Printer,
  ChevronUp, ChevronDown, Minus, Target, UserCheck, Clock, AlertCircle,
  Award, Scale, Lightbulb, BarChart3
} from 'lucide-react';

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' }
];

const KPICard = ({ title, current, target, previous, status, icon: Icon, format = 'percent', subtitle }) => {
  const change = previous !== undefined ? current - previous : null;
  const isPositive = change > 0;
  const isNeutral = change === 0;

  const formatValue = (val) => {
    if (format === 'percent') return `${val}%`;
    if (format === 'currency') return `Rp ${val?.toLocaleString('id-ID') || 0}`;
    if (format === 'number') return val?.toLocaleString('id-ID') || 0;
    return val;
  };

  const statusColors = {
    good: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
    critical: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
  };

  return (
    <Card className="relative overflow-hidden">
      <CardContent className="p-4 sm:p-6">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1 sm:space-y-2 min-w-0 flex-1">
            <p className="text-xs sm:text-sm text-muted-foreground truncate">{title}</p>
            <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
              <span className="text-2xl sm:text-3xl font-bold">{formatValue(current)}</span>
              {target && (
                <span className="text-xs sm:text-sm text-muted-foreground">/ {formatValue(target)}</span>
              )}
            </div>
            {subtitle && <p className="text-xs text-muted-foreground line-clamp-2">{subtitle}</p>}
            {change !== null && (
              <div className="flex items-center gap-1 text-xs sm:text-sm">
                {isPositive ? (
                  <ChevronUp className="w-3 h-3 sm:w-4 sm:h-4 text-green-600 flex-shrink-0" />
                ) : isNeutral ? (
                  <Minus className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400 flex-shrink-0" />
                ) : (
                  <ChevronDown className="w-3 h-3 sm:w-4 sm:h-4 text-red-600 flex-shrink-0" />
                )}
                <span className={`truncate ${isPositive ? 'text-green-600' : isNeutral ? 'text-gray-500' : 'text-red-600'}`}>
                  {isPositive ? '+' : ''}{change.toFixed(1)}{format === 'percent' ? '%' : ''} <span className="hidden xs:inline">vs last month</span>
                </span>
              </div>
            )}
          </div>
          <div className={`p-2 sm:p-3 rounded-full flex-shrink-0 ${statusColors[status] || 'bg-gray-100'}`}>
            <Icon className="w-5 h-5 sm:w-6 sm:h-6" />
          </div>
        </div>
        {target && (
          <div className="mt-3 sm:mt-4">
            <Progress value={Math.min((current / target) * 100, 100)} className="h-2" />
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const InsightCard = ({ type, category, message }) => {
  const config = {
    success: { icon: CheckCircle2, bg: 'bg-green-50 dark:bg-green-900/20', border: 'border-green-200 dark:border-green-800', text: 'text-green-800 dark:text-green-300' },
    warning: { icon: AlertTriangle, bg: 'bg-amber-50 dark:bg-amber-900/20', border: 'border-amber-200 dark:border-amber-800', text: 'text-amber-800 dark:text-amber-300' },
    critical: { icon: AlertCircle, bg: 'bg-red-50 dark:bg-red-900/20', border: 'border-red-200 dark:border-red-800', text: 'text-red-800 dark:text-red-300' },
    info: { icon: Lightbulb, bg: 'bg-blue-50 dark:bg-blue-900/20', border: 'border-blue-200 dark:border-blue-800', text: 'text-blue-800 dark:text-blue-300' }
  };

  const { icon: Icon, bg, border, text } = config[type] || config.info;

  return (
    <div className={`p-3 sm:p-4 rounded-lg ${bg} border ${border}`}>
      <div className="flex items-start gap-2 sm:gap-3">
        <Icon className={`w-4 h-4 sm:w-5 sm:h-5 ${text} flex-shrink-0 mt-0.5`} />
        <div className="min-w-0 flex-1">
          <Badge variant="outline" className={`mb-1 text-xs ${text} border-current`}>{category}</Badge>
          <p className={`text-xs sm:text-sm ${text}`}>{message}</p>
        </div>
      </div>
    </div>
  );
};

const StaffPerformanceRow = ({ staff, rank, avgTasks }) => {
  const workloadColor = {
    overworked: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    underworked: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
    balanced: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
  };

  return (
    <div className="p-4 bg-muted/30 rounded-lg">
      {/* Mobile layout */}
      <div className="flex flex-col gap-3 sm:hidden">
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-primary text-sm">
            {rank}
          </div>
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-muted flex items-center justify-center overflow-hidden">
            {staff.photo_url ? (
              <img src={staff.photo_url} alt={staff.user_name} className="w-full h-full object-cover" />
            ) : (
              <Users className="w-5 h-5 text-muted-foreground" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{staff.user_name}</p>
            <p className="text-xs text-muted-foreground">{staff.role || 'Staff'}</p>
          </div>
          <Badge className={`${workloadColor[staff.workload_status]} text-xs`}>{staff.workload_status}</Badge>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 bg-background/50 rounded">
            <p className="text-lg font-bold">{staff.tasks_completed}</p>
            <p className="text-xs text-muted-foreground">tasks</p>
          </div>
          <div className="p-2 bg-background/50 rounded">
            <p className="text-lg font-bold">{staff.members_contacted}</p>
            <p className="text-xs text-muted-foreground">members</p>
          </div>
          <div className="p-2 bg-background/50 rounded">
            <p className="text-lg font-bold">{staff.active_days}</p>
            <p className="text-xs text-muted-foreground">days</p>
          </div>
        </div>
      </div>

      {/* Desktop layout */}
      <div className="hidden sm:flex items-center gap-4">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-primary">
          {rank}
        </div>
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-muted flex items-center justify-center overflow-hidden">
          {staff.photo_url ? (
            <img src={staff.photo_url} alt={staff.user_name} className="w-full h-full object-cover" />
          ) : (
            <Users className="w-5 h-5 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate">{staff.user_name}</p>
          <p className="text-xs text-muted-foreground">{staff.role || 'Staff'}</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-bold">{staff.tasks_completed}</p>
          <p className="text-xs text-muted-foreground">tasks</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-bold">{staff.members_contacted}</p>
          <p className="text-xs text-muted-foreground">members</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-bold">{staff.active_days}</p>
          <p className="text-xs text-muted-foreground">active days</p>
        </div>
        <Badge className={workloadColor[staff.workload_status]}>{staff.workload_status}</Badge>
      </div>
    </div>
  );
};

export const Reports = () => {
  const { t } = useTranslation();
  const reportRef = useRef(null);
  const [activeTab, setActiveTab] = useState('monthly');
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);

  // Use TanStack Query for data fetching - leverages prefetched cache from route loader
  const { data: monthlyReport, isLoading: loadingMonthly } = useQuery({
    queryKey: ['monthly-report', selectedYear, selectedMonth],
    queryFn: () => api.get(`/reports/monthly?year=${selectedYear}&month=${selectedMonth}`).then(res => res.data),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  const { data: staffReport, isLoading: loadingStaff } = useQuery({
    queryKey: ['staff-performance', selectedYear, selectedMonth],
    queryFn: () => api.get(`/reports/staff-performance?year=${selectedYear}&month=${selectedMonth}`).then(res => res.data),
    staleTime: 1000 * 60 * 5,
  });

  const { data: yearlyReport, isLoading: loadingYearly } = useQuery({
    queryKey: ['yearly-summary', selectedYear],
    queryFn: () => api.get(`/reports/yearly-summary?year=${selectedYear}`).then(res => res.data),
    staleTime: 1000 * 60 * 5,
  });

  const loading = loadingMonthly || loadingStaff || loadingYearly;

  const [exporting, setExporting] = useState(false);
  const [printing, setPrinting] = useState(false);

  // Shared function to fetch PDF
  const fetchPDF = async () => {
    const response = await api.get(`/reports/monthly/pdf?year=${selectedYear}&month=${selectedMonth}`, {
      responseType: 'arraybuffer'  // Use arraybuffer for binary data
    });
    // Create blob from arraybuffer with explicit MIME type
    return new Blob([response.data], { type: 'application/pdf' });
  };

  const handlePrint = async () => {
    setPrinting(true);
    try {
      const blob = await fetchPDF();
      const url = window.URL.createObjectURL(blob);

      // Open PDF in new window and print
      const printWindow = window.open(url, '_blank');
      if (printWindow) {
        printWindow.onload = () => {
          printWindow.focus();
          printWindow.print();
        };
      }

      // Clean up after a delay
      setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (error) {
      console.error('Error printing PDF:', error);
      alert('Failed to generate PDF for printing. Please try again.');
    } finally {
      setPrinting(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const blob = await fetchPDF();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Pastoral_Care_Report_${MONTHS.find(m => m.value === selectedMonth)?.label}_${selectedYear}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      // Delay URL revocation to ensure download completes
      setTimeout(() => window.URL.revokeObjectURL(url), 5000);
    } catch (error) {
      console.error('Error exporting PDF:', error);
      alert('Failed to export PDF. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-40" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  const exec = monthlyReport?.executive_summary || {};
  const kpis = monthlyReport?.kpis || {};
  const ministry = monthlyReport?.ministry_highlights || {};

  return (
    <div className="space-y-4 sm:space-y-6 print:space-y-4 overflow-hidden" ref={reportRef}>
      {/* Header */}
      <div className="flex flex-col gap-4 print:hidden">
        <div>
          <h1 className="text-2xl sm:text-3xl font-playfair font-bold text-foreground flex items-center gap-2">
            <FileText className="w-6 h-6 sm:w-8 sm:h-8 text-teal-600 flex-shrink-0" />
            {t('reports.title') || 'Reports'}
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">{t('reports.subtitle') || 'Management reports and staff performance analytics'}</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex gap-2">
            <Select value={String(selectedMonth)} onValueChange={(v) => setSelectedMonth(Number(v))}>
              <SelectTrigger className="flex-1 sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MONTHS.map(m => (
                  <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(selectedYear)} onValueChange={(v) => setSelectedYear(Number(v))}>
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {years.map(y => (
                  <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handlePrint} disabled={printing} className="flex-1 sm:flex-none">
              <Printer className={`w-4 h-4 mr-2 ${printing ? 'animate-pulse' : ''}`} />
              <span className="hidden xs:inline">{printing ? 'Generating...' : 'Print'}</span>
              <span className="xs:hidden">{printing ? '...' : 'Print'}</span>
            </Button>
            <Button onClick={handleExportPDF} disabled={exporting} className="flex-1 sm:flex-none bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50">
              <Download className={`w-4 h-4 mr-2 ${exporting ? 'animate-pulse' : ''}`} />
              <span className="hidden xs:inline">{exporting ? 'Generating...' : 'Export PDF'}</span>
              <span className="xs:hidden">{exporting ? '...' : 'PDF'}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Print Header */}
      <div className="hidden print:block mb-6">
        <h1 className="text-2xl font-bold text-center">Pastoral Care Monthly Report</h1>
        <p className="text-center text-gray-600">
          {monthlyReport?.report_period?.month_name} {monthlyReport?.report_period?.year}
        </p>
        <p className="text-center text-sm text-gray-500">
          Generated: {new Date(monthlyReport?.report_period?.generated_at).toLocaleDateString()}
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="print:hidden">
        <TabsList className="grid w-full grid-cols-3 lg:w-auto lg:inline-grid">
          <TabsTrigger value="monthly" className="flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Monthly Report
          </TabsTrigger>
          <TabsTrigger value="staff" className="flex items-center gap-2">
            <Users className="w-4 h-4" />
            Staff Performance
          </TabsTrigger>
          <TabsTrigger value="yearly" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Yearly Summary
          </TabsTrigger>
        </TabsList>

        {/* Monthly Management Report */}
        <TabsContent value="monthly" className="space-y-6 mt-6">
          {/* Executive Summary */}
          <Card className="print:shadow-none print:border-2">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2">
                <Target className="w-5 h-5 text-teal-600" />
                Executive Summary - {monthlyReport?.report_period?.month_name} {monthlyReport?.report_period?.year}
              </CardTitle>
              <CardDescription>
                Key metrics and performance overview for church leadership
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4 mb-4 sm:mb-6">
                <div className="text-center p-3 sm:p-4 bg-teal-50 dark:bg-teal-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-teal-700 dark:text-teal-400">{exec.total_members || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Total Members</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-green-700 dark:text-green-400">{exec.active_members || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Active</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-amber-700 dark:text-amber-400">{exec.at_risk_members || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">At Risk</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-red-700 dark:text-red-400">{exec.inactive_members || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Inactive</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                <div className="p-3 sm:p-4 border rounded-lg">
                  <p className="text-xs sm:text-sm text-muted-foreground">Care Events This Month</p>
                  <p className="text-xl sm:text-2xl font-bold">{exec.total_care_events || 0}</p>
                  <div className="flex gap-2 mt-1 text-xs">
                    <span className="text-green-600">{exec.completed_events || 0} completed</span>
                    <span className="text-amber-600">{exec.pending_events || 0} pending</span>
                  </div>
                </div>
                <div className="p-3 sm:p-4 border rounded-lg">
                  <p className="text-xs sm:text-sm text-muted-foreground">Completion Rate</p>
                  <p className="text-xl sm:text-2xl font-bold">{exec.completion_rate || 0}%</p>
                  <Progress value={exec.completion_rate || 0} className="h-2 mt-2" />
                </div>
                <div className="p-3 sm:p-4 border rounded-lg">
                  <p className="text-xs sm:text-sm text-muted-foreground">Financial Aid Distributed</p>
                  <p className="text-xl sm:text-2xl font-bold truncate">Rp {(exec.financial_aid_total || 0).toLocaleString('id-ID')}</p>
                  <p className="text-xs text-muted-foreground">{exec.financial_aid_recipients || 0} recipients</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 print:grid-cols-2">
            <KPICard
              title="Care Completion Rate"
              current={kpis.care_completion_rate?.current || 0}
              target={kpis.care_completion_rate?.target}
              previous={kpis.care_completion_rate?.previous}
              status={kpis.care_completion_rate?.status}
              icon={CheckCircle2}
            />
            <KPICard
              title="Member Engagement"
              current={kpis.member_engagement_rate?.current || 0}
              target={kpis.member_engagement_rate?.target}
              status={kpis.member_engagement_rate?.status}
              icon={UserCheck}
              subtitle={`${kpis.member_engagement_rate?.at_risk_percentage || 0}% at risk · ${kpis.member_engagement_rate?.disconnected_percentage || 0}% disconnected`}
            />
            <KPICard
              title="Member Reach Rate"
              current={kpis.member_reach_rate?.current || 0}
              target={kpis.member_reach_rate?.target}
              status={kpis.member_reach_rate?.status}
              icon={Users}
              subtitle={`${kpis.member_reach_rate?.members_contacted || 0} contacted`}
            />
            <KPICard
              title="Birthday Completion"
              current={kpis.birthday_completion_rate?.current || 0}
              target={kpis.birthday_completion_rate?.target}
              status={kpis.birthday_completion_rate?.status}
              icon={Gift}
              subtitle={`${kpis.birthday_completion_rate?.celebrated || 0} celebrated${kpis.birthday_completion_rate?.ignored ? ` · ${kpis.birthday_completion_rate.ignored} skipped` : ''} of ${kpis.birthday_completion_rate?.total || 0}`}
            />
          </div>

          {/* Ministry Highlights */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                    <Heart className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Grief Support</p>
                    <p className="text-lg font-bold">{ministry.grief_support?.families_supported || 0} families</p>
                    <p className="text-xs text-muted-foreground">{ministry.grief_support?.total_touchpoints || 0} touchpoints</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <Activity className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Hospital Visits</p>
                    <p className="text-lg font-bold">{ministry.hospital_visits?.patients_visited || 0} patients</p>
                    <p className="text-xs text-muted-foreground">{ministry.hospital_visits?.total_visits || 0} visits</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-pink-100 dark:bg-pink-900/30 rounded-lg">
                    <Gift className="w-5 h-5 text-pink-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Birthdays</p>
                    <p className="text-lg font-bold">{ministry.birthday_ministry?.celebrated || 0} celebrated</p>
                    <p className="text-xs text-muted-foreground">
                      {ministry.birthday_ministry?.ignored ? `${ministry.birthday_ministry.ignored} skipped · ` : ''}
                      {ministry.birthday_ministry?.total_birthdays || 0} total
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                    <DollarSign className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Financial Aid</p>
                    <p className="text-lg font-bold">Rp {(ministry.financial_aid?.total_amount || 0).toLocaleString('id-ID')}</p>
                    <p className="text-xs text-muted-foreground">{ministry.financial_aid?.recipients || 0} recipients</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Care Breakdown & Weekly Trend */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            <Card>
              <CardHeader className="pb-2 sm:pb-4">
                <CardTitle className="text-base sm:text-lg">Care Events by Type</CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-6">
                <div className="space-y-2 sm:space-y-3">
                  {monthlyReport?.care_breakdown?.map((care, i) => (
                    <div key={i} className="flex items-center justify-between gap-3 p-2 sm:p-3 bg-muted/30 rounded-lg">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm sm:text-base truncate">{care.label}</p>
                        <p className="text-xs text-muted-foreground">
                          {care.completed} done, {care.pending} pending
                        </p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="text-base sm:text-lg font-bold">{care.total}</p>
                        <p className="text-xs text-muted-foreground">total</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2 sm:pb-4">
                <CardTitle className="text-base sm:text-lg">Weekly Activity Trend</CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-6">
                <div className="w-full overflow-x-auto">
                  <div className="min-w-[280px]">
                    <AreaChart
                      data={monthlyReport?.engagement_trend || []}
                      dataKey="contacts_made"
                      xAxisKey="week"
                      color="#14b8a6"
                      height={220}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Insights & Recommendations */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            <Card>
              <CardHeader className="pb-2 sm:pb-4">
                <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
                  <Lightbulb className="w-4 h-4 sm:w-5 sm:h-5 text-amber-500 flex-shrink-0" />
                  Strategic Insights
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-6">
                <div className="space-y-2 sm:space-y-3">
                  {monthlyReport?.insights?.length > 0 ? (
                    monthlyReport.insights.map((insight, i) => (
                      <InsightCard key={i} {...insight} />
                    ))
                  ) : (
                    <p className="text-muted-foreground text-center py-6 sm:py-8 text-sm">No specific insights for this period</p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2 sm:pb-4">
                <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
                  <Target className="w-4 h-4 sm:w-5 sm:h-5 text-teal-600 flex-shrink-0" />
                  Action Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-6">
                <div className="space-y-2 sm:space-y-3">
                  {monthlyReport?.recommendations?.length > 0 ? (
                    monthlyReport.recommendations.map((rec, i) => (
                      <div key={i} className="flex items-start gap-2 sm:gap-3 p-2 sm:p-3 bg-teal-50 dark:bg-teal-900/20 rounded-lg">
                        <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-teal-600 text-white flex items-center justify-center text-xs sm:text-sm font-bold flex-shrink-0">
                          {i + 1}
                        </div>
                        <p className="text-xs sm:text-sm text-teal-800 dark:text-teal-300">{rec}</p>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted-foreground text-center py-6 sm:py-8 text-sm">No specific recommendations for this period</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Month Comparison */}
          <Card>
            <CardHeader className="pb-2 sm:pb-4">
              <CardTitle className="text-base sm:text-lg">Comparison with Previous Month</CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4">
                {Object.entries(monthlyReport?.comparison || {}).map(([key, data]) => (
                  <div key={key} className="p-2 sm:p-4 border rounded-lg text-center">
                    <p className="text-xs sm:text-sm text-muted-foreground capitalize truncate">{key.replace(/_/g, ' ')}</p>
                    <p className="text-lg sm:text-2xl font-bold truncate">{typeof data.current === 'number' && data.current > 1000 ? data.current.toLocaleString('id-ID') : data.current}</p>
                    <div className={`flex items-center justify-center gap-1 text-xs sm:text-sm ${data.change > 0 ? 'text-green-600' : data.change < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      {data.change > 0 ? <TrendingUp className="w-3 h-3 sm:w-4 sm:h-4 flex-shrink-0" /> : data.change < 0 ? <TrendingDown className="w-3 h-3 sm:w-4 sm:h-4 flex-shrink-0" /> : <Minus className="w-3 h-3 sm:w-4 sm:h-4 flex-shrink-0" />}
                      <span className="truncate">{data.change > 0 ? '+' : ''}{typeof data.change === 'number' && Math.abs(data.change) > 1000 ? data.change.toLocaleString('id-ID') : data.change}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Staff Performance Tab */}
        <TabsContent value="staff" className="space-y-6 mt-6">
          {/* Team Overview */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-teal-600" />
                Team Workload Overview - {staffReport?.report_period?.month_name} {staffReport?.report_period?.year}
              </CardTitle>
              <CardDescription>
                Monitor workload distribution to prevent burnout and ensure equitable task assignment
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4 mb-4 sm:mb-6">
                <div className="text-center p-3 sm:p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold">{staffReport?.team_stats?.total_staff || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Total Staff</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-green-700 dark:text-green-400">{staffReport?.team_stats?.balanced_count || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Balanced</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-red-700 dark:text-red-400">{staffReport?.team_stats?.overworked_count || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Overworked</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-amber-700 dark:text-amber-400">{staffReport?.team_stats?.underworked_count || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Underworked</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                <div className="p-3 sm:p-4 border rounded-lg text-center">
                  <p className="text-xs sm:text-sm text-muted-foreground">Total Tasks Completed</p>
                  <p className="text-xl sm:text-2xl font-bold">{staffReport?.team_stats?.total_tasks_completed || 0}</p>
                </div>
                <div className="p-3 sm:p-4 border rounded-lg text-center">
                  <p className="text-xs sm:text-sm text-muted-foreground">Avg Tasks/Staff</p>
                  <p className="text-xl sm:text-2xl font-bold">{staffReport?.team_stats?.average_tasks_per_staff || 0}</p>
                </div>
                <div className="p-3 sm:p-4 border rounded-lg text-center">
                  <p className="text-xs sm:text-sm text-muted-foreground">Max - Min Difference</p>
                  <p className="text-xl sm:text-2xl font-bold">{(staffReport?.team_stats?.max_tasks || 0) - (staffReport?.team_stats?.min_tasks || 0)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Staff Recommendations */}
          {staffReport?.recommendations?.length > 0 && (
            <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-amber-800 dark:text-amber-400">
                  <AlertTriangle className="w-5 h-5" />
                  Workload Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {staffReport.recommendations.map((rec, i) => (
                    <div key={i} className={`p-4 rounded-lg ${rec.priority === 'high' ? 'bg-red-100 dark:bg-red-900/30' : rec.priority === 'medium' ? 'bg-amber-100 dark:bg-amber-900/30' : 'bg-blue-100 dark:bg-blue-900/30'}`}>
                      <div className="flex items-start gap-3">
                        <Badge variant={rec.priority === 'high' ? 'destructive' : rec.priority === 'medium' ? 'warning' : 'default'}>
                          {rec.priority}
                        </Badge>
                        <div>
                          <p className="font-medium">{rec.message}</p>
                          <p className="text-sm text-muted-foreground mt-1">{rec.action}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Top Performers */}
          {staffReport?.top_performers?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Award className="w-5 h-5 text-amber-500" />
                  Top Performers
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {staffReport.top_performers.slice(0, 3).map((staff, i) => (
                    <div key={staff.user_id} className={`p-4 rounded-lg text-center ${i === 0 ? 'bg-amber-100 dark:bg-amber-900/30 border-2 border-amber-400' : 'bg-muted/30'}`}>
                      <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center mb-3 ${i === 0 ? 'bg-amber-400 text-white' : i === 1 ? 'bg-gray-300 text-gray-700' : 'bg-orange-300 text-orange-800'}`}>
                        {staff.photo_url ? (
                          <img src={staff.photo_url} alt={staff.user_name} className="w-full h-full rounded-full object-cover" />
                        ) : (
                          <span className="text-2xl font-bold">#{i + 1}</span>
                        )}
                      </div>
                      <p className="font-bold">{staff.user_name}</p>
                      <p className="text-2xl font-bold text-teal-600">{staff.tasks_completed}</p>
                      <p className="text-sm text-muted-foreground">tasks completed</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Individual Staff Performance */}
          <Card>
            <CardHeader>
              <CardTitle>Individual Staff Performance</CardTitle>
              <CardDescription>Detailed breakdown of each staff member's activities</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {staffReport?.staff_performance?.map((staff, i) => (
                  <StaffPerformanceRow
                    key={staff.user_id}
                    staff={staff}
                    rank={i + 1}
                    avgTasks={staffReport?.team_stats?.average_tasks_per_staff || 0}
                  />
                ))}
                {(!staffReport?.staff_performance || staffReport.staff_performance.length === 0) && (
                  <p className="text-muted-foreground text-center py-8">No staff activity recorded for this period</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Yearly Summary Tab */}
        <TabsContent value="yearly" className="space-y-4 sm:space-y-6 mt-4 sm:mt-6">
          <Card>
            <CardHeader className="pb-2 sm:pb-4">
              <CardTitle className="text-base sm:text-lg">Yearly Summary - {yearlyReport?.report_period?.year}</CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4">
                <div className="text-center p-3 sm:p-4 bg-teal-50 dark:bg-teal-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-teal-700 dark:text-teal-400">{yearlyReport?.yearly_totals?.total_members || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Members</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-blue-700 dark:text-blue-400">{yearlyReport?.yearly_totals?.total_care_events || 0}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Care Events</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <p className="text-2xl sm:text-3xl font-bold text-green-700 dark:text-green-400">{yearlyReport?.yearly_totals?.completion_rate || 0}%</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Completion</p>
                </div>
                <div className="text-center p-3 sm:p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                  <p className="text-lg sm:text-2xl font-bold text-amber-700 dark:text-amber-400 truncate">Rp {(yearlyReport?.yearly_totals?.total_financial_aid || 0).toLocaleString('id-ID')}</p>
                  <p className="text-xs sm:text-sm text-muted-foreground">Financial Aid</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2 sm:pb-4">
              <CardTitle className="text-base sm:text-lg">Monthly Trend</CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              <div className="w-full overflow-x-auto">
                <div className="min-w-[300px]">
                  <AreaChart
                    data={yearlyReport?.monthly_breakdown || []}
                    dataKey="total_events"
                    xAxisKey="month_name"
                    color="#14b8a6"
                    height={250}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2 sm:pb-4">
              <CardTitle className="text-base sm:text-lg">Care Events by Type (Year Total)</CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
                {yearlyReport?.care_by_type?.map((care, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 p-3 sm:p-4 bg-muted/30 rounded-lg">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm sm:text-base truncate">{care.label}</p>
                      <p className="text-xs text-muted-foreground">{care.completed} of {care.total} completed</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-xl sm:text-2xl font-bold">{care.total}</p>
                      <Progress value={(care.completed / care.total) * 100 || 0} className="h-2 w-16 sm:w-24" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Print-only content */}
      <div className="hidden print:block">
        {/* The content above will be printed */}
      </div>
    </div>
  );
};

export default Reports;
