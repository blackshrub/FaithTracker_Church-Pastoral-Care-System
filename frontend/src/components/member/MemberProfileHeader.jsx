/**
 * Member Profile Header Component
 * Displays member photo, name, contact info, and engagement status
 */

import React, { memo } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { MemberAvatar } from '@/components/MemberAvatar';
import { EngagementBadge } from '@/components/EngagementBadge';
import { formatDate } from '@/lib/dateUtils';

// Memoized to prevent re-renders when member detail state changes
export const MemberProfileHeader = memo(({
  member,
  onAddCareEvent,
  backLink = '/members'
}) => {
  const { t } = useTranslation();

  if (!member) return null;

  return (
    <div className="max-w-full">
      {/* Back Button */}
      <Link to={backLink}>
        <Button variant="ghost" size="sm" className="mb-4 h-10">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Members
        </Button>
      </Link>

      {/* Profile Section */}
      <div className="flex flex-col sm:flex-row items-start gap-4 sm:gap-6 max-w-full">
        {/* Profile Photo - enables shared element transition from list/dashboard */}
        <div className="shrink-0">
          <MemberAvatar
            member={member}
            size="xl"
            className="w-20 h-20 sm:w-32 sm:h-32"
            enableTransition
          />
        </div>

        {/* Member Info */}
        <div className="flex-1 min-w-0 w-full">
          <div className="space-y-3">
            {/* Name and Contact - with view transition */}
            <div className="min-w-0">
              <h1
                className="text-2xl sm:text-3xl font-playfair font-bold text-foreground"
                style={{ viewTransitionName: member.id ? `member-name-${member.id}` : undefined }}
              >
                {member.name}
              </h1>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                {member.phone && (
                  <a
                    href={`tel:${member.phone}`}
                    className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1"
                  >
                    📞 {member.phone}
                  </a>
                )}
              </div>
            </div>

            {/* Engagement Badge & Last Contact */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <EngagementBadge
                status={member.engagement_status}
                days={member.days_since_last_contact}
              />
              {member.last_contact_date && (
                <span className="text-xs sm:text-sm text-muted-foreground">
                  {t('last_contact')}: {formatDate(member.last_contact_date, 'dd MMM yyyy')}
                </span>
              )}
            </div>
          </div>

          {/* Add Care Event Button */}
          <Button
            onClick={onAddCareEvent}
            className="bg-teal-500 hover:bg-teal-600 text-white w-full sm:w-auto mt-4 h-12 min-w-0"
            data-testid="add-care-event-button"
          >
            <Plus className="w-4 h-4 mr-2 flex-shrink-0" />
            <span className="truncate">{t('add_care_event')}</span>
          </Button>
        </div>
      </div>
    </div>
  );
});

MemberProfileHeader.propTypes = {
  member: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string.isRequired,
    phone: PropTypes.string,
    photo_url: PropTypes.string,
    engagement_status: PropTypes.string,
    days_since_last_contact: PropTypes.number,
    last_contact_date: PropTypes.string
  }),
  onAddCareEvent: PropTypes.func.isRequired,
  backLink: PropTypes.string
};

export default MemberProfileHeader;
