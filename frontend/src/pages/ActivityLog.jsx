/**
 * Activity Log Page - Staff accountability and action tracking
 * Displays complete audit trail of all user actions with filtering and CSV export
 * Tracks WHO did WHAT on WHICH member with timezone-aware timestamps
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import api from '@/lib/api';
import { Calendar, Download, Filter, User, Activity, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';

const ActivityLog = () => {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [campusTimezone, setCampusTimezone] = useState('Asia/Jakarta');  // Default, will load from API
  
  // Filters
  const [selectedUser, setSelectedUser] = useState('all');
  const [selectedAction, setSelectedAction] = useState('all');
  const [startDate, setStartDate] = useState(getDefaultStartDate());
  const [endDate, setEndDate] = useState(getDefaultEndDate());

  // Format date/time using campus timezone - Fix UTC timestamp handling
  const formatDateTime = (dateString) => {
    try {
      // Ensure timestamp is treated as UTC by adding Z if missing
      let utcTimestamp = dateString;
      if (typeof dateString === 'string' && !dateString.endsWith('Z') && !dateString.includes('+')) {
        utcTimestamp = dateString.replace(' ', 'T') + 'Z';  // Convert to ISO format with Z
      }
      
      const date = new Date(utcTimestamp);
      if (isNaN(date.getTime())) {
        return { date: 'Invalid date', time: '' };
      }
      
      // Use Intl.DateTimeFormat for proper timezone handling
      const dateFormatter = new Intl.DateTimeFormat('id-ID', {
        timeZone: campusTimezone,
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
      
      const timeFormatter = new Intl.DateTimeFormat('id-ID', {
        timeZone: campusTimezone,
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      });
      
      const formattedDate = dateFormatter.format(date);
      const formattedTime = timeFormatter.format(date);
      
      // Debug: console.log(`Input: ${dateString} | UTC: ${utcTimestamp} | Output: ${formattedDate} ${formattedTime} | TZ: ${campusTimezone}`);
      
      return {
        date: formattedDate,
        time: formattedTime
      };
    } catch (error) {
      console.error('Error formatting date:', dateString, 'timezone:', campusTimezone, error);
      return { 
        date: new Date(dateString).toLocaleDateString('id-ID'),
        time: new Date(dateString).toLocaleTimeString('id-ID', {hour: '2-digit', minute: '2-digit', hour12: false})
      };
    }
  };


  // Load campus timezone
  useEffect(() => {
    const loadCampusTimezone = async () => {
      try {
        const userResponse = await api.get('/auth/me');

        const campusId = userResponse.data.campus_id;
        if (campusId && campusId !== 'campus_id') {
          const campusResponse = await api.get(`/campuses/${campusId}`);
          setCampusTimezone(campusResponse.data.timezone || 'Asia/Jakarta');
        }
      } catch (error) {
        console.error('Error loading campus timezone:', error);
        // Fallback to Asia/Jakarta
      }
    };

    loadCampusTimezone();
  }, []);


  // Get default start date (30 days ago)
  function getDefaultStartDate() {
    const date = new Date();
    date.setDate(date.getDate() - 30);
    return date.toISOString().split('T')[0];
  }

  // Get default end date (today)
  function getDefaultEndDate() {
    return new Date().toISOString().split('T')[0];
  }

  useEffect(() => {
    fetchSummary();
    fetchAllUsers();
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [selectedUser, selectedAction, startDate, endDate]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();

      if (selectedUser !== 'all') params.append('user_id', selectedUser);
      if (selectedAction !== 'all') params.append('action_type', selectedAction);
      if (startDate) params.append('start_date', new Date(startDate).toISOString());
      if (endDate) {
        const endDateTime = new Date(endDate);
        endDateTime.setHours(23, 59, 59, 999);
        params.append('end_date', endDateTime.toISOString());
      }
      params.append('limit', '200');

      const response = await api.get(`/activity-logs?${params.toString()}`);
      setLogs(response.data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await api.get('/activity-logs/summary');
      setSummary(response.data);
    } catch (error) {
      console.error('Error fetching summary:', error);
    }
  };

  const fetchAllUsers = async () => {
    try {
      const response = await api.get('/users');
      setUsers(response.data);
    } catch (error) {
      console.error('Error fetching users:', error);
    }
  };

  const exportToCSV = () => {
    // CSV headers
    const headers = ['Date', 'Time', 'Staff Member', 'Action', 'Member', 'Event Type', 'Notes'];
    
    // CSV rows with timezone-aware formatting
    const rows = logs.map(log => {
      const { date, time } = formatDateTime(log.created_at);
      return [
        date,
        time,
        log.user_name,
        formatActionType(log.action_type),
        log.member_name || '-',
        log.event_type ? formatEventType(log.event_type) : '-',
        log.notes || '-'
      ];
    });

    // Create CSV content
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `activity_log_${startDate}_to_${endDate}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const formatActionType = (actionType) => {
    return actionType.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const formatEventType = (eventType) => {
    return eventType.replace('_', ' ').split(' ').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const getActionIcon = (actionType) => {
    const icons = {
      complete_task: '✓',
      ignore_task: '⊘',
      send_reminder: '📧',
      stop_schedule: '⏹',
      clear_ignored: '🔄'
    };
    return icons[actionType] || '•';
  };

  const getActionColor = (actionType) => {
    const colors = {
      complete_task: 'text-green-600 bg-green-50',
      ignore_task: 'text-yellow-600 bg-yellow-50',
      send_reminder: 'text-blue-600 bg-blue-50',
      stop_schedule: 'text-red-600 bg-red-50',
      clear_ignored: 'text-purple-600 bg-purple-50'
    };
    return colors[actionType] || 'text-gray-600 bg-gray-50';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {t('Activity Log')}
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t('Track staff accountability and care activities')}
          </p>
        </div>
        <Button onClick={exportToCSV} className="gap-2" data-testid="export-csv-btn">
          <Download className="h-4 w-4" />
          {t('Export CSV')}
        </Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">
                {t('Total Activities')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">
                {summary.total_activities}
              </div>
              <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">
                {t('Active Staff')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">
                {summary.active_users}
              </div>
              <p className="text-xs text-gray-500 mt-1">Contributing members</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">
                {t('Tasks Completed')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-600">
                {summary.action_breakdown.find(a => a._id === 'complete_task')?.count || 0}
              </div>
              <p className="text-xs text-gray-500 mt-1">Care tasks</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">
                {t('Reminders Sent')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-600">
                {summary.action_breakdown.find(a => a._id === 'send_reminder')?.count || 0}
              </div>
              <p className="text-xs text-gray-500 mt-1">WhatsApp messages</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            {t('Filters')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Staff Member Filter */}
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                {t('Staff Member')}
              </label>
              <Select value={selectedUser} onValueChange={setSelectedUser}>
                <SelectTrigger data-testid="filter-user">
                  <SelectValue placeholder={t('All Staff')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('All Staff')}</SelectItem>
                  {users.map(user => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Action Type Filter */}
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                {t('Action Type')}
              </label>
              <Select value={selectedAction} onValueChange={setSelectedAction}>
                <SelectTrigger data-testid="filter-action">
                  <SelectValue placeholder={t('All Actions')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('All Actions')}</SelectItem>
                  <SelectItem value="complete_task">{t('Complete Task')}</SelectItem>
                  <SelectItem value="ignore_task">{t('Ignore Task')}</SelectItem>
                  <SelectItem value="send_reminder">{t('Send Reminder')}</SelectItem>
                  <SelectItem value="stop_schedule">{t('Stop Schedule')}</SelectItem>
                  <SelectItem value="clear_ignored">{t('Clear Ignored')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Date Range Filter */}
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                {t('Start Date')}
              </label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                data-testid="filter-start-date"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                {t('End Date')}
              </label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                data-testid="filter-end-date"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Activity Log Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            {t('Activity History')} ({logs.length} {t('records')})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              {t('No activity records found for the selected filters')}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="activity-log-table">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('Date & Time')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('Staff Member')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('Action')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('Member')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('Event Type')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('Notes')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-sm text-gray-900 dark:text-gray-100">
                          {formatDateTime(log.created_at).date}
                        </div>
                        <div className="text-xs text-gray-500">
                          {formatDateTime(log.created_at).time}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0">
                            {log.user_photo_url ? (
                              <img
                                src={log.user_photo_url.startsWith('http') ? log.user_photo_url : `${import.meta.env.VITE_BACKEND_URL}${log.user_photo_url}`}
                                alt={log.user_name}
                                className="h-8 w-8 rounded-full object-cover"
                              />
                            ) : (
                              <div className="h-8 w-8 bg-blue-100 rounded-full flex items-center justify-center">
                                <User className="h-4 w-4 text-blue-600" />
                              </div>
                            )}
                          </div>
                          <div className="ml-3">
                            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                              {log.user_name}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getActionColor(log.action_type)}`}>
                          <span className="mr-1">{getActionIcon(log.action_type)}</span>
                          {formatActionType(log.action_type)}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                        {log.member_name || '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {log.event_type ? formatEventType(log.event_type) : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
                        {log.notes || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ActivityLog;
