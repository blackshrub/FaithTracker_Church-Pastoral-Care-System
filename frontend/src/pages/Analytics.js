import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = [
  'hsl(45, 90%, 65%)',
  'hsl(330, 75%, 70%)',
  'hsl(240, 15%, 45%)',
  'hsl(25, 85%, 62%)',
  'hsl(15, 70%, 58%)',
  'hsl(200, 40%, 50%)',
  'hsl(140, 55%, 48%)',
  'hsl(180, 42%, 45%)'
];

export const Analytics = () => {
  const { t } = useTranslation();
  const [eventsByType, setEventsByType] = useState([]);
  const [griefCompletion, setGriefCompletion] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadAnalytics();
  }, []);
  
  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const [eventsRes, griefRes] = await Promise.all([
        axios.get(`${API}/analytics/care-events-by-type`),
        axios.get(`${API}/analytics/grief-completion-rate`)
      ]);
      
      setEventsByType(eventsRes.data);
      setGriefCompletion(griefRes.data);
    } catch (error) {
      console.error('Error loading analytics:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return <div className="space-y-6"><Skeleton className="h-96 w-full" /></div>;
  }
  
  const chartData = eventsByType.map(item => ({
    name: t(`event_types.${item.type}`),
    count: item.count
  }));
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-manrope font-bold text-foreground">{t('analytics')}</h1>
        <p className="text-muted-foreground mt-1">Pastoral care insights and trends</p>
      </div>
      
      {/* Grief Completion Stats */}
      {griefCompletion && griefCompletion.total_stages > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Grief Support Completion Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Stages</p>
                <p className="text-2xl font-bold">{griefCompletion.total_stages}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Completed</p>
                <p className="text-2xl font-bold text-green-600">{griefCompletion.completed_stages}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="text-2xl font-bold text-yellow-600">{griefCompletion.pending_stages}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Completion Rate</p>
                <p className="text-2xl font-bold text-primary-600">{griefCompletion.completion_rate}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Care Events Distribution */}
      <Card>
        <CardHeader>
          <CardTitle>Care Events by Type</CardTitle>
        </CardHeader>
        <CardContent>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={120}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-12">No care events data</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Analytics;