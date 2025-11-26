/**
 * Dashboard Stats Cards Component
 * Displays 4 key metrics: Total Members, Tasks Due Today, Overdue Follow-ups, Members Needing Care
 */

import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '@/components/ui/card';
import { Users, Bell, Heart, AlertTriangle } from 'lucide-react';

export const DashboardStats = ({
  totalMembers = 805,
  birthdaysToday = [],
  todayTasks = [],
  griefDue = [],
  accidentFollowUp = [],
  financialAidDue = [],
  atRiskMembers = [],
  disconnectedMembers = []
}) => {
  const { t } = useTranslation();

  const tasksDueToday = birthdaysToday.filter(b => !b.completed).length +
                        todayTasks.filter(t => !t.completed).length;

  const overdueFollowups = griefDue.length + accidentFollowUp.length + financialAidDue.length;

  const membersNeedingCare = atRiskMembers.length + disconnectedMembers.length;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 max-w-full">
      {/* Total Members */}
      <Card className="card-border-left-teal shadow-sm hover:shadow-md transition-all min-w-0">
        <CardContent className="p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-xs sm:text-sm text-muted-foreground mb-1">{t('total_members')}</p>
              <p className="text-2xl sm:text-4xl font-playfair font-bold">{totalMembers}</p>
            </div>
            <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
              <Users className="w-5 h-5 sm:w-7 sm:h-7 text-teal-600" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tasks Due Today */}
      <Card className="card-border-left-amber shadow-sm hover:shadow-md transition-all min-w-0">
        <CardContent className="p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-xs sm:text-sm text-muted-foreground mb-1">Tasks Due Today</p>
              <p className="text-2xl sm:text-4xl font-playfair font-bold">{tasksDueToday}</p>
            </div>
            <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <Bell className="w-5 h-5 sm:w-7 sm:h-7 text-amber-600" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Overdue Follow-ups */}
      <Card className="card-border-left-pink shadow-sm hover:shadow-md transition-all min-w-0">
        <CardContent className="p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-xs sm:text-sm text-muted-foreground mb-1">Overdue Follow-ups</p>
              <p className="text-2xl sm:text-4xl font-playfair font-bold">{overdueFollowups}</p>
            </div>
            <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-pink-100 flex items-center justify-center flex-shrink-0">
              <Heart className="w-5 h-5 sm:w-7 sm:h-7 text-pink-600" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Members Needing Care */}
      <Card className="card-border-left-purple shadow-sm hover:shadow-md transition-all min-w-0">
        <CardContent className="p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-xs sm:text-sm text-muted-foreground mb-1">Members Needing Care</p>
              <p className="text-2xl sm:text-4xl font-playfair font-bold">{membersNeedingCare}</p>
            </div>
            <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-5 h-5 sm:w-7 sm:h-7 text-purple-600" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

DashboardStats.propTypes = {
  totalMembers: PropTypes.number,
  birthdaysToday: PropTypes.array,
  todayTasks: PropTypes.array,
  griefDue: PropTypes.array,
  accidentFollowUp: PropTypes.array,
  financialAidDue: PropTypes.array,
  atRiskMembers: PropTypes.array,
  disconnectedMembers: PropTypes.array
};

export default DashboardStats;
