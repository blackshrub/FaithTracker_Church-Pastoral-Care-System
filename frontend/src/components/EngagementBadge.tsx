import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';
import type { EngagementStatus } from '@/types';

interface EngagementBadgeProps {
  status: EngagementStatus;
  days?: number;
}

const variants: Record<string, string> = {
  active: 'bg-green-100 text-green-800 border-green-300',
  at_risk: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  inactive: 'bg-red-100 text-red-800 border-red-300',
};

export const EngagementBadge = ({ status, days }: EngagementBadgeProps) => {
  const { t } = useTranslation();

  return (
    <Badge
      className={variants[status] || variants.inactive}
      data-testid={`engagement-badge-${status}`}
    >
      {t(status)} {days != null && days > 0 && `(${days}d)`}
    </Badge>
  );
};
