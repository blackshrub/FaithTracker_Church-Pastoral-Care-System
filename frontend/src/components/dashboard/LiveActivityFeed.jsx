/**
 * LiveActivityFeed - Real-time activity stream component
 *
 * Displays live updates from team members using SSE.
 * Shows who completed what task, with animations for new items.
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useActivityStream, formatActivityMessage } from '@/hooks/useActivityStream';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Activity, Wifi, WifiOff, Bell, Check, X, UserPlus, Edit, Trash2, Clock } from 'lucide-react';
import { formatRelativeTime } from '@/lib/dateUtils';
import { cn } from '@/lib/utils';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

// Action type icons
const ACTION_ICONS = {
  complete: Check,
  ignore: X,
  create_event: Bell,
  update_event: Edit,
  delete_event: Trash2,
  create_member: UserPlus,
  update_member: Edit,
  delete_member: Trash2,
  complete_stage: Check,
  ignore_stage: X,
  send_reminder: Bell,
  distribute_aid: Check,
};

// Action type colors
const ACTION_COLORS = {
  complete: 'bg-green-100 text-green-700',
  ignore: 'bg-gray-100 text-gray-600',
  create_event: 'bg-blue-100 text-blue-700',
  update_event: 'bg-amber-100 text-amber-700',
  delete_event: 'bg-red-100 text-red-700',
  create_member: 'bg-teal-100 text-teal-700',
  update_member: 'bg-amber-100 text-amber-700',
  delete_member: 'bg-red-100 text-red-700',
  complete_stage: 'bg-green-100 text-green-700',
  ignore_stage: 'bg-gray-100 text-gray-600',
  send_reminder: 'bg-blue-100 text-blue-700',
  distribute_aid: 'bg-green-100 text-green-700',
};

const getInitials = (name) => {
  if (!name) return '?';
  const parts = name.trim().split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
};

const ActivityItem = ({ activity, isNew }) => {
  const { t } = useTranslation();
  const Icon = ACTION_ICONS[activity.action_type] || Activity;
  const colorClass = ACTION_COLORS[activity.action_type] || 'bg-gray-100 text-gray-600';

  const photoUrl = activity.user_photo_url
    ? (activity.user_photo_url.startsWith('http') ? activity.user_photo_url : `${BACKEND_URL}${activity.user_photo_url}`)
    : null;

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-3 rounded-lg transition-all duration-500',
        isNew ? 'bg-teal-50 animate-pulse' : 'bg-white hover:bg-gray-50'
      )}
    >
      <Avatar className="h-8 w-8 flex-shrink-0">
        {photoUrl ? (
          <AvatarImage src={photoUrl} alt={activity.user_name} />
        ) : null}
        <AvatarFallback className="bg-teal-100 text-teal-700 text-xs">
          {getInitials(activity.user_name)}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-900">
          <span className="font-medium">{activity.user_name}</span>
          {' '}
          <span className="text-gray-600">
            {t(`activity.${activity.action_type}`, {
              member: activity.member_name,
              defaultValue: formatActivityMessage(activity).replace(activity.user_name + ' ', '')
            })}
          </span>
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {formatRelativeTime(activity.timestamp)}
        </p>
      </div>

      <div className={cn('p-1.5 rounded-full flex-shrink-0', colorClass)}>
        <Icon className="h-3.5 w-3.5" />
      </div>
    </div>
  );
};

export function LiveActivityFeed({ maxItems = 10, className }) {
  const { t } = useTranslation();
  const [newActivityIds, setNewActivityIds] = useState(new Set());

  const { isConnected, activities, error } = useActivityStream({
    enabled: true,
    maxActivities: maxItems,
    onActivity: (activity) => {
      // Mark as new for animation
      setNewActivityIds((prev) => new Set([...prev, activity.id]));
      // Remove "new" status after animation
      setTimeout(() => {
        setNewActivityIds((prev) => {
          const next = new Set(prev);
          next.delete(activity.id);
          return next;
        });
      }, 3000);
    },
  });

  if (error) {
    return null; // Silently fail - activity feed is optional
  }

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Activity className="h-4 w-4 text-teal-600" />
            {t('dashboard.live_activity', 'Team Activity')}
          </CardTitle>
          <Badge
            variant="outline"
            className={cn(
              'text-xs',
              isConnected ? 'border-green-300 text-green-700' : 'border-gray-300 text-gray-500'
            )}
          >
            {isConnected ? (
              <>
                <Wifi className="h-3 w-3 mr-1" />
                {t('live', 'Live')}
              </>
            ) : (
              <>
                <WifiOff className="h-3 w-3 mr-1" />
                {t('connecting', 'Connecting...')}
              </>
            )}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {activities.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('dashboard.no_recent_activity', 'No recent team activity')}</p>
            <p className="text-xs mt-1">{t('dashboard.activity_will_appear', 'Activity from teammates will appear here')}</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {activities.map((activity) => (
              <ActivityItem
                key={activity.id}
                activity={activity}
                isNew={newActivityIds.has(activity.id)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default LiveActivityFeed;
