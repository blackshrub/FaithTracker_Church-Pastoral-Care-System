import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Users } from 'lucide-react';

import { MemberLink } from '@/components/LinkWithPrefetch';
import api from '@/lib/api';
import { formatDate } from '@/lib/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import LazyImage from '@/components/LazyImage';
import PieChart from '@/components/charts/PieChart';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

const COLORS = [
  '#14b8a6', // Teal
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#a78bfa', // Purple
  '#06b6d4', // Cyan
  '#84cc16', // Lime
  '#f97316'  // Orange
];

const MemberNameWithPhoto = ({ member, memberId }) => {
  const getInitials = (name) => {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return parts[0][0] + parts[parts.length - 1][0];
    }
    return name.substring(0, 2);
  };

  // Handle both absolute URLs (from external CDN) and relative paths (local uploads)
  const photoUrl = member?.photo_url
    ? (member.photo_url.startsWith('http') ? member.photo_url : `${BACKEND_URL}${member.photo_url}`)
    : null;

  return (
    <MemberLink memberId={memberId} className="flex items-center gap-3 hover:text-teal-700">
      <div className="w-8 h-8 rounded-full overflow-hidden bg-teal-100 flex items-center justify-center">
        {photoUrl ? (
          <LazyImage
            src={photoUrl}
            alt={member.name}
            className="w-full h-full object-cover"
            placeholderClassName="w-full h-full bg-teal-100 flex items-center justify-center text-teal-700 text-xs font-semibold"
          />
        ) : (
          <span className="text-teal-700 font-semibold text-xs">
            {getInitials(member.name)}
          </span>
        )}
      </div>
      <span className="font-medium hover:underline">{member.name}</span>
    </MemberLink>
  );
};

export const FinancialAid = () => {
  const { t } = useTranslation();
  const [recipients, setRecipients] = useState([]);
  const [loadingRecipients, setLoadingRecipients] = useState(false);

  // Use TanStack Query for data fetching with long cache time
  const { data: financialData, isLoading: loading } = useQuery({
    queryKey: ['financial-aid-data'],
    queryFn: async () => {
      const [summaryRes, eventsRes, membersRes] = await Promise.all([
        api.get('/financial-aid/summary'),
        api.get('/care-events?event_type=financial_aid'),
        api.get('/members?limit=1000')
      ]);

      // Add member photos to events
      const memberMap = {};
      (membersRes.data || []).forEach(m => memberMap[m.id] = {
        name: m.name,
        photo_url: m.photo_url
      });

      const eventsWithPhotos = (eventsRes.data || []).map(event => ({
        ...event,
        member_photo_url: memberMap[event.member_id]?.photo_url
      }));

      return {
        summary: summaryRes.data || {},
        aidEvents: eventsWithPhotos
      };
    },
    staleTime: 1000 * 60 * 5, // 5 minutes - data stays fresh longer
    gcTime: 1000 * 60 * 10, // 10 minutes - keep in cache longer
    retry: 2,
  });

  const summary = financialData?.summary || null;
  const aidEvents = financialData?.aidEvents || [];

  const loadRecipients = async () => {
    try {
      setLoadingRecipients(true);
      const response = await api.get('/financial-aid/recipients');
      setRecipients(response.data);
    } catch (_error) {
      // Error handled silently - UI will show empty state
    } finally {
      setLoadingRecipients(false);
    }
  };

  if (loading) {
    return <div className="space-y-6 max-w-full"><Skeleton className="h-96 w-full" /></div>;
  }
  
  const chartData = summary?.by_type ? Object.entries(summary.by_type).map(([type, data]) => ({
    name: t(`aid_types.${type}`),
    value: data.total_amount
  })) : [];
  
  return (
    <div className="space-y-6 max-w-full">
      <div className="min-w-0">
        <h1 className="text-3xl font-playfair font-bold text-foreground">{t('financial_aid')}</h1>
        <p className="text-muted-foreground mt-1">{t('financial_assistance_tracking')}</p>
      </div>
      
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">{t('total_aid')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">
              Rp {(summary?.total_amount || 0).toLocaleString('id-ID')}
            </p>
          </CardContent>
        </Card>
        
        <Dialog>
          <DialogTrigger asChild>
            <Card className="cursor-pointer hover:bg-accent/50 transition-colors" onClick={loadRecipients}>
              <CardHeader>
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {t('total_recipients')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-foreground">{summary?.total_count || 0}</p>
                <p className="text-xs text-muted-foreground mt-1">Click to view details</p>
              </CardContent>
            </Card>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{t('total_recipients')}</DialogTitle>
            </DialogHeader>
            {loadingRecipients ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : recipients.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">{t('empty_states.no_results_found')}</p>
            ) : (
              <div className="space-y-2">
                {recipients.map((recipient) => (
                  <div 
                    key={recipient.member_id} 
                    className="block p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex-1">
                        <MemberNameWithPhoto 
                          member={{ name: recipient.member_name, photo_url: recipient.photo_url }} 
                          memberId={recipient.member_id} 
                        />
                        <p className="text-xs text-muted-foreground mt-1 ml-11">
                          {recipient.aid_count} {t('aid_event')}{recipient.aid_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                      <p className="font-semibold text-green-700">
                        Rp {(recipient.total_amount || 0).toLocaleString('id-ID')}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </DialogContent>
        </Dialog>
        
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">{t('aid_types_label')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">
              {summary?.by_type ? Object.keys(summary.by_type).length : 0}
            </p>
          </CardContent>
        </Card>
      </div>
      
      {/* Chart and Recent Aid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>{t('aid_distribution')}</CardTitle>
          </CardHeader>
          <CardContent>
            {chartData.length > 0 ? (
              <PieChart
                data={chartData}
                colors={COLORS}
                height={300}
                formatValue={(value) => `Rp ${value.toLocaleString('id-ID')}`}
              />
            ) : (
              <p className="text-sm text-muted-foreground text-center py-12">{t('empty_states.no_financial_aid')}</p>
            )}
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>{t('recent_aid')}</CardTitle>
          </CardHeader>
          <CardContent>
            {aidEvents.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">{t('empty_states.no_financial_aid')}</p>
            ) : (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {aidEvents.map((event) => (
                  <div key={event.id} className="p-3 bg-muted/30 rounded-lg">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        {event.member_id && event.member_name ? (
                          <MemberNameWithPhoto 
                            member={{ name: event.member_name, photo_url: event.member_photo_url }} 
                            memberId={event.member_id} 
                          />
                        ) : (
                          <p className="font-medium text-sm text-muted-foreground">Unknown Member</p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1 ml-11">
                          {t(`aid_types.${event.aid_type || 'other'}`)} - {formatDate(event.event_date, 'dd MMM yyyy')}
                        </p>
                      </div>
                      <p className="font-semibold text-green-700">
                        Rp {(event.aid_amount || 0).toLocaleString('id-ID')}
                      </p>
                    </div>
                    {event.aid_notes && (
                      <p className="text-xs text-muted-foreground mt-1 ml-11">{event.aid_notes}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default FinancialAid;