import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar as CalIcon, ChevronLeft, ChevronRight, Users, Heart, Hospital, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const Calendar = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedDateEvents, setSelectedDateEvents] = useState([]);
  const [detailsOpen, setDetailsOpen] = useState(false);
  
  useEffect(() => {
    loadEvents();
  }, [currentDate]);
  
  const loadEvents = async () => {
    try {
      const response = await axios.get(`${API}/care-events`);
      setEvents(response.data);
    } catch (error) {
      toast.error('Failed to load events');
    }
  };
  
  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const days = [];
    
    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push(new Date(year, month, i));
    }
    return days;
  };
  
  const days = getDaysInMonth(currentDate);
  const monthName = currentDate.toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
  
  const handleDateClick = (day, dayEvents) => {
    if (dayEvents.length > 0) {
      setSelectedDate(day);
      setSelectedDateEvents(dayEvents);
      setDetailsOpen(true);
    }
  };
  
  // Group events by type for better display
  const groupEventsByType = (eventList) => {
    const grouped = {};
    eventList.forEach(e => {
      if (!grouped[e.event_type]) grouped[e.event_type] = [];
      grouped[e.event_type].push(e);
    });
    return grouped;
  };
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-playfair font-bold">Calendar View</h1>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setCurrentDate(new Date(currentDate.setMonth(currentDate.getMonth() - 1)))}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-lg font-semibold min-w-[200px] text-center">{monthName}</span>
          <Button size="sm" variant="outline" onClick={() => setCurrentDate(new Date(currentDate.setMonth(currentDate.getMonth() + 1)))}>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      <Card>
        <CardContent className="p-6">
          <div className="grid grid-cols-7 gap-2">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
              <div key={day} className="text-center font-semibold text-sm text-muted-foreground p-2">{day}</div>
            ))}
            {days.map((day) => {
              const dayEvents = events.filter(e => e.event_date === day.toISOString().split('T')[0]);
              return (
                <div 
                  key={day.toISOString()} 
                  className={`border rounded-lg p-2 min-h-[80px] transition-all ${dayEvents.length > 0 ? 'hover:bg-teal-50 cursor-pointer hover:shadow-md' : 'hover:bg-muted/50'}`}
                  onClick={() => handleDateClick(day, dayEvents)}
                >
                  <div className="text-sm font-semibold mb-1">{day.getDate()}</div>
                  {dayEvents.slice(0, 2).map(e => (
                    <div key={e.id} className="text-xs bg-teal-100 text-teal-700 rounded px-1 mb-1 truncate">
                      {e.event_type.replace('_', ' ')}
                    </div>
                  ))}
                  {dayEvents.length > 2 && <div className="text-xs text-muted-foreground font-semibold">+{dayEvents.length - 2} more</div>}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Calendar;