import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { DollarSign, Users } from 'lucide-react';
import LazyImage from '@/components/LazyImage';
import { format } from 'date-fns';

// Safe date formatter
const formatDate = (dateStr, formatStr = 'dd MMM yyyy') => {
  try {
    return format(new Date(dateStr), formatStr);
  } catch (e) {
    return dateStr;
  }
};

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = [
  'hsl(140, 55%, 48%)',
  'hsl(200, 40%, 50%)', 
  'hsl(15, 70%, 58%)',
  'hsl(25, 85%, 62%)',
  'hsl(330, 75%, 70%)',
  'hsl(180, 42%, 45%)',
  'hsl(240, 15%, 45%)'
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

  const photoUrl = member?.photo_url ? `${BACKEND_URL}/api${member.photo_url}` : null;

  return (
    <Link to={`/members/${memberId}`} className="flex items-center gap-3 hover:text-teal-700">
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
    </Link>
  );
};

export const FinancialAid = () => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState(null);
  const [aidEvents, setAidEvents] = useState([]);
  const [recipients, setRecipients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingRecipients, setLoadingRecipients] = useState(false);
  
  useEffect(() => {
    loadFinancialAidData();
  }, []);
  
  const loadFinancialAidData = async () => {
    try {
      setLoading(true);
      const [summaryRes, eventsRes] = await Promise.all([
        axios.get(`${API}/financial-aid/summary`),
        axios.get(`${API}/care-events?event_type=financial_aid`)
      ]);
      
      setSummary(summaryRes.data);
      setAidEvents(eventsRes.data);
    } catch (error) {
      console.error('Error loading financial aid:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadRecipients = async () => {
    try {
      setLoadingRecipients(true);
      const response = await axios.get(`${API}/financial-aid/recipients`);
      setRecipients(response.data);
    } catch (error) {
      console.error('Error loading recipients:', error);
    } finally {
      setLoadingRecipients(false);
    }
  };
  
  if (loading) {
    return <div className="space-y-6"><Skeleton className="h-96 w-full" /></div>;
  }
  
  const chartData = summary?.by_type ? Object.entries(summary.by_type).map(([type, data]) => ({
    name: t(`aid_types.${type}`),
    value: data.total_amount
  })) : [];
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-manrope font-bold text-foreground">{t('financial_aid')}</h1>
        <p className="text-muted-foreground mt-1">Financial assistance tracking and analytics</p>
      </div>
      
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Total Aid (All Time)</CardTitle>
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
                  Total Recipients
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
              <DialogTitle>Financial Aid Recipients</DialogTitle>
            </DialogHeader>
            {loadingRecipients ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : recipients.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No recipients found.</p>
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
                          {recipient.aid_count} aid event{recipient.aid_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                      <p className="font-semibold text-green-700">
                        Rp {recipient.total_amount?.toLocaleString('id-ID')}
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
            <CardTitle className="text-sm font-medium">Aid Types</CardTitle>
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
            <CardTitle>Aid Distribution by Type</CardTitle>
          </CardHeader>
          <CardContent>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `Rp ${value.toLocaleString('id-ID')}`} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-12">No financial aid data</p>
            )}
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Recent Financial Aid</CardTitle>
          </CardHeader>
          <CardContent>
            {aidEvents.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No financial aid recorded.</p>
            ) : (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {aidEvents.map((event) => (
                  <div key={event.id} className="p-3 bg-muted/30 rounded-lg">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        {event.member_id && event.member_name ? (
                          <Link 
                            to={`/members/${event.member_id}`}
                            className="font-medium text-sm text-primary hover:underline"
                          >
                            {event.member_name}
                          </Link>
                        ) : (
                          <p className="font-medium text-sm text-muted-foreground">Unknown Member</p>
                        )}
                        <p className="font-medium text-sm text-muted-foreground">
                          {t(`aid_types.${event.aid_type}`)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatDate(event.event_date, 'dd MMM yyyy')}
                        </p>
                      </div>
                      <p className="font-semibold text-green-700">
                        Rp {event.aid_amount?.toLocaleString('id-ID')}
                      </p>
                    </div>
                    {event.aid_notes && (
                      <p className="text-xs text-muted-foreground mt-1">{event.aid_notes}</p>
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