/**
 * Reusable Task Card Component
 * Used for birthdays, grief support, accidents, and financial aid tasks
 */

import React, { memo } from 'react';
import PropTypes from 'prop-types';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { MemberAvatar } from '@/components/MemberAvatar';
import { MemberLink } from '@/components/LinkWithPrefetch';
import { Check } from 'lucide-react';

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

// Memoized to prevent unnecessary re-renders in list contexts
export const TaskCard = memo(({
  event,
  config = {
    bgClass: 'bg-gray-50',
    borderClass: 'border-gray-200',
    btnClass: 'bg-gray-500 hover:bg-gray-600',
    ringClass: 'ring-gray-400'
  },
  onComplete,
  children, // Additional content like badges
  actionLabel = 'Mark Complete',
  completedLabel = 'Completed',
  contactLabel = 'Contact WhatsApp',
  triggerHaptic = () => {},
  // Bulk selection props
  selectable = false,
  selected = false,
  onSelectionChange,
}) => {
  return (
    <article
      className={`p-4 ${config.bgClass} rounded-lg border ${selected ? 'border-teal-500 ring-2 ring-teal-200' : config.borderClass} relative hover:shadow-lg transition-all`}
      aria-label={`Task for ${event.member_name}${event.days_overdue > 0 ? `, ${event.days_overdue} days overdue` : ''}`}
    >
      {/* Overdue Badge - Top Right */}
      {event.days_overdue > 0 && (
        <span className={`absolute top-3 ${selectable ? 'right-10' : 'right-3'} px-2 py-1 bg-red-500 text-white text-xs font-semibold rounded shadow-sm z-10`} aria-hidden="true">
          {event.days_overdue}d overdue
        </span>
      )}

      {/* Selection Checkbox - Top Right */}
      {selectable && (
        <div className="absolute top-3 right-3 z-10">
          <Checkbox
            checked={selected}
            onCheckedChange={() => onSelectionChange && onSelectionChange(event.id)}
            className="h-5 w-5 border-2 data-[state=checked]:bg-teal-600 data-[state=checked]:border-teal-600"
            aria-label={`Select task for ${event.member_name}`}
          />
        </div>
      )}

      <div className="flex items-start gap-3 mb-3">
        {/* Avatar with colored ring */}
        <div className={`flex-shrink-0 rounded-full ring-2 ${config.ringClass}`}>
          <MemberAvatar
            member={{
              name: event.member_name,
              photo_url: event.member_photo_url
            }}
            size="md"
          />
        </div>

        <div className="flex-1 min-w-0">
          <MemberLink
            memberId={event.member_id}
            className="font-semibold text-base hover:text-teal-600"
          >
            {event.member_name}
          </MemberLink>
          {event.member_phone && (
            <a
              href={`tel:${event.member_phone}`}
              className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1 mt-1"
            >
              📞 {event.member_phone}
            </a>
          )}
          <div className="text-sm text-muted-foreground mt-1">
            {children}
          </div>
        </div>
      </div>

      {/* Actions - Horizontal compact layout */}
      <div className="flex gap-2">
        <Button
          size="default"
          className={`${config.btnClass} text-white h-11 flex-1 min-w-0`}
          asChild
        >
          <a
            href={formatPhoneForWhatsApp(event.member_phone)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
            </svg>
            <span className="truncate">{contactLabel}</span>
          </a>
        </Button>
        {event.completed ? (
          <Button
            size="default"
            variant="outline"
            disabled
            className="bg-white text-green-700 border-green-300 h-11 flex-1 min-w-0"
          >
            <Check className="w-4 h-4 mr-1" />
            <span className="truncate">{completedLabel}</span>
          </Button>
        ) : (
          <Button
            size="default"
            variant="outline"
            onClick={() => {
              triggerHaptic();
              onComplete && onComplete(event.id);
            }}
            className="h-11 flex-1 min-w-0 bg-white hover:bg-gray-50"
          >
            <Check className="w-4 h-4 mr-1" />
            <span className="truncate">{actionLabel}</span>
          </Button>
        )}
      </div>
    </article>
  );
});

TaskCard.propTypes = {
  event: PropTypes.shape({
    id: PropTypes.string,
    member_id: PropTypes.string.isRequired,
    member_name: PropTypes.string.isRequired,
    member_phone: PropTypes.string,
    member_photo_url: PropTypes.string,
    days_overdue: PropTypes.number,
    completed: PropTypes.bool
  }).isRequired,
  config: PropTypes.shape({
    bgClass: PropTypes.string,
    borderClass: PropTypes.string,
    btnClass: PropTypes.string,
    ringClass: PropTypes.string
  }),
  onComplete: PropTypes.func,
  children: PropTypes.node,
  actionLabel: PropTypes.string,
  completedLabel: PropTypes.string,
  contactLabel: PropTypes.string,
  triggerHaptic: PropTypes.func,
  // Bulk selection
  selectable: PropTypes.bool,
  selected: PropTypes.bool,
  onSelectionChange: PropTypes.func,
};

export default TaskCard;
