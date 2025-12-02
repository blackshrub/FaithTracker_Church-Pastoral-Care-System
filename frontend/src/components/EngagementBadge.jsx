import React from 'react';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';

export const EngagementBadge = ({ status, days }) => {
  const { t } = useTranslation();
  
  const variants = {
    active: 'bg-green-100 text-green-800 border-green-300',
    at_risk: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    inactive: 'bg-red-100 text-red-800 border-red-300'
  };
  
  return (
    <Badge 
      className={variants[status] || variants.inactive}
      data-testid={`engagement-badge-${status}`}
    >
      {t(status)} {days > 0 && `(${days}d)`}
    </Badge>
  );
};