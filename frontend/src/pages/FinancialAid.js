import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { DollarSign } from 'lucide-react';
import { format } from 'date-fns';

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

export const FinancialAid = () => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState(null);
  const [aidEvents, setAidEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  
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
        
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Total Recipients</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{summary?.total_count || 0}</p>
          </CardContent>
        </Card>
        
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
                      <div>
                        <p className="font-medium text-sm">{t(`aid_types.${event.aid_type}`)}</p>
                        <p className="text-xs text-muted-foreground">
                          {format(new Date(event.event_date), 'dd MMM yyyy')}
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