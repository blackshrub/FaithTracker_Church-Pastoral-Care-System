import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar as CalIcon, ChevronLeft, ChevronRight, Users, Heart, Hospital, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

export const Calendar = () => {
  const { t } = useTranslation();
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
      const response = await api.get('/care-events');
      setEvents(response.data);
    } catch (error) {
      toast.error(t('toasts.failed_load_events'));
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
              // Use local date string (YYYY-MM-DD) without UTC conversion
              const localDateStr = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
              const dayEvents = events.filter(e => e.event_date === localDateStr);
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
      
      {/* Event Details Dialog */}
      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Events on {selectedDate && selectedDate.toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' })}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {Object.entries(groupEventsByType(selectedDateEvents)).map(([type, typeEvents]) => (
              <Card key={type} className="card-border-left-teal">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    {type === 'birthday' && <Users className="w-5 h-5 text-amber-600" />}
                    {type === 'grief_loss' && <Heart className="w-5 h-5 text-pink-600" />}
                    {type === 'hospital_visit' && <Hospital className="w-5 h-5 text-blue-600" />}
                    {type === 'financial_aid' && <DollarSign className="w-5 h-5 text-green-600" />}
                    {type.replace('_', ' ').toUpperCase()} ({typeEvents.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {typeEvents.map(event => (
                      <div key={event.id} className="p-3 bg-muted/30 rounded-lg">
                        <p className="font-semibold">{event.title}</p>
                        {event.member_name && (
                          <p className="text-sm text-muted-foreground">Member: {event.member_name}</p>
                        )}
                        {event.description && (
                          <p className="text-sm text-muted-foreground">{event.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Calendar;