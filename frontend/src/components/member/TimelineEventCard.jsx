/**
 * Timeline Event Card Component
 * Reusable card for displaying care events in timeline format
 */

import React from 'react';
import PropTypes from 'prop-types';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { EventTypeBadge } from '@/components/EventTypeBadge';
import { CheckCircle2, MoreVertical, Trash2 } from 'lucide-react';
import { format } from 'date-fns/format';

const formatDate = (dateStr, formatStr = 'dd MMM yyyy') => {
  try {
    return format(new Date(dateStr), formatStr);
  } catch (e) {
    return dateStr;
  }
};

const getEventColors = (eventType) => {
  const celebrationTypes = ['birthday', 'childbirth', 'new_house'];
  const careTypes = ['grief_loss', 'accident_illness', 'hospital_visit'];
  const aidTypes = ['financial_aid'];

  if (celebrationTypes.includes(eventType)) {
    return {
      dotColor: 'bg-amber-500',
      borderClass: 'card-border-left-amber'
    };
  } else if (careTypes.includes(eventType)) {
    return {
      dotColor: 'bg-pink-500',
      borderClass: 'card-border-left-pink'
    };
  } else if (aidTypes.includes(eventType)) {
    return {
      dotColor: 'bg-purple-500',
      borderClass: 'card-border-left-purple'
    };
  }

  return {
    dotColor: 'bg-teal-500',
    borderClass: 'card-border-left-teal'
  };
};

export const TimelineEventCard = ({
  event,
  onDelete,
  children  // For additional content like grief timelines
}) => {
  const isIgnored = event.ignored === true;
  const isCompleted = event.completed === true;
  const { dotColor, borderClass } = getEventColors(event.event_type);

  return (
    <div className="flex gap-3 sm:gap-4 pb-6 relative" data-testid={`care-event-${event.id}`}>
      {/* Timeline Date Marker */}
      <div className="flex flex-col items-center shrink-0 w-12 sm:w-16">
        {/* Date Circle */}
        <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-white border-2 border-gray-200 shadow-md flex flex-col items-center justify-center relative z-10">
          <div className="text-sm sm:text-base font-bold leading-none">
            {formatDate(event.event_date, 'dd')}
          </div>
          <div className="text-[9px] sm:text-[10px] leading-none uppercase opacity-70 mt-0.5">
            {formatDate(event.event_date, 'MMM')}
          </div>
        </div>
        {/* Colored Dot Indicator */}
        <div className={`w-3 h-3 sm:w-4 sm:h-4 rounded-full ${dotColor} border-2 border-background shadow-sm mt-1 relative z-10`}></div>
      </div>

      {/* Event Content Card */}
      <Card className={`flex-1 ${borderClass} shadow-sm hover:shadow-md transition-all min-w-0 card ${isIgnored || isCompleted ? 'opacity-60' : ''}`}>
        <CardContent className="p-3 sm:p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              {/* Event Type & Status Badges */}
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <EventTypeBadge type={event.event_type} />
                {isCompleted && (
                  <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Completed
                  </span>
                )}
                {isIgnored && !isCompleted && (
                  <span className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded">
                    Ignored
                  </span>
                )}
              </div>

              {/* Event Title */}
              <h5 className="font-playfair font-semibold text-sm sm:text-base text-foreground mb-2">
                {event.title}
              </h5>

              {/* Event Description */}
              {event.description && (
                <p className="text-sm whitespace-pre-line font-bold text-foreground mb-2">
                  {event.description}
                </p>
              )}

              {/* Grief Relationship */}
              {event.grief_relationship && (
                <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                  Relationship: {event.grief_relationship.charAt(0).toUpperCase() + event.grief_relationship.slice(1)}
                </p>
              )}

              {/* Hospital Name */}
              {event.hospital_name && event.hospital_name !== 'N/A' && event.hospital_name !== 'null' && event.hospital_name !== 'NULL' && (
                <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                  Hospital: {event.hospital_name}
                </p>
              )}

              {/* Financial Aid Amount */}
              {event.aid_amount && (
                <p className="text-sm text-green-700 font-medium mt-2">
                  {event.aid_type && `${event.aid_type} - `}
                  Rp {event.aid_amount.toLocaleString('id-ID')}
                </p>
              )}

              {/* Created By */}
              {event.created_by_user_name && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                  <span className="font-medium">Created by:</span> {event.created_by_user_name}
                </p>
              )}

              {/* Completed By */}
              {event.completed && event.completed_by_user_name && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-3 pt-2 border-t border-gray-200 dark:border-gray-700">
                  <span className="font-medium">Completed by:</span> {event.completed_by_user_name}
                  {event.completed_at && ` on ${new Date(event.completed_at).toLocaleDateString()}`}
                </p>
              )}

              {/* Ignored By */}
              {event.ignored && event.ignored_by_name && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-3 pt-2 border-t border-gray-200 dark:border-gray-700">
                  <span className="font-medium">Ignored by:</span> {event.ignored_by_name}
                  {event.ignored_at && ` on ${new Date(event.ignored_at).toLocaleDateString()}`}
                </p>
              )}

              {/* Additional Content (e.g., grief timeline) */}
              {children}
            </div>

            {/* Actions Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="ghost" className="min-h-[44px] min-w-[44px] shrink-0">
                  <MoreVertical className="w-5 h-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => onDelete && onDelete(event.id)}
                  className="text-red-600"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

TimelineEventCard.propTypes = {
  event: PropTypes.shape({
    id: PropTypes.string.isRequired,
    event_type: PropTypes.string.isRequired,
    event_date: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    completed: PropTypes.bool,
    ignored: PropTypes.bool,
    grief_relationship: PropTypes.string,
    hospital_name: PropTypes.string,
    aid_type: PropTypes.string,
    aid_amount: PropTypes.number,
    created_by_user_name: PropTypes.string,
    completed_by_user_name: PropTypes.string,
    completed_at: PropTypes.string,
    ignored_by_name: PropTypes.string,
    ignored_at: PropTypes.string
  }).isRequired,
  onDelete: PropTypes.func,
  children: PropTypes.node
};

export default TimelineEventCard;
