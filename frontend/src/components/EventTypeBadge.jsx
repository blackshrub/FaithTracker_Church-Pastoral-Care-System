import React from 'react';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import { Calendar, Baby, Heart, Home, Ambulance, Hospital, DollarSign, Phone } from 'lucide-react';

export const EventTypeBadge = ({ type }) => {
  const { t } = useTranslation();
  
  const config = {
    birthday: { icon: Calendar, color: 'hsl(45, 90%, 65%)', bg: 'hsl(45, 90%, 95%)' },
    childbirth: { icon: Baby, color: 'hsl(330, 75%, 70%)', bg: 'hsl(330, 75%, 97%)' },
    grief_loss: { icon: Heart, color: 'hsl(240, 15%, 45%)', bg: 'hsl(240, 15%, 95%)' },
    new_house: { icon: Home, color: 'hsl(25, 85%, 62%)', bg: 'hsl(25, 85%, 97%)' },
    accident_illness: { icon: Ambulance, color: 'hsl(15, 70%, 58%)', bg: 'hsl(15, 70%, 96%)' },
    hospital_visit: { icon: Hospital, color: 'hsl(200, 40%, 50%)', bg: 'hsl(200, 40%, 95%)' },
    financial_aid: { icon: DollarSign, color: 'hsl(140, 55%, 48%)', bg: 'hsl(140, 55%, 95%)' },
    regular_contact: { icon: Phone, color: 'hsl(180, 42%, 45%)', bg: 'hsl(180, 35%, 97%)' }
  };
  
  const typeConfig = config[type] || config.regular_contact;
  const Icon = typeConfig.icon;
  
  return (
    <Badge 
      className="text-xs font-medium border-0"
      style={{ 
        backgroundColor: typeConfig.bg, 
        color: typeConfig.color 
      }}
      data-testid={`event-badge-${type}`}
    >
      <Icon className="w-3 h-3 mr-1" />
      {t(`event_types.${type}`)}
    </Badge>
  );
};