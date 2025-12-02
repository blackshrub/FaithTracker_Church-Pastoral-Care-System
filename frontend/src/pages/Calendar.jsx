import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import api from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ChevronLeft, ChevronRight, Users, Heart, Hospital, DollarSign, Check, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';
import { MemberAvatar } from '@/components/MemberAvatar';

// Format phone for WhatsApp link
const formatPhoneForWhatsApp = (phone) => {
  if (!phone) return '#';
  let formatted = phone;
  if (formatted.startsWith('0')) {
    formatted = '62' + formatted.substring(1);
  } else if (formatted.startsWith('+')) {
    formatted = formatted.substring(1);
  }
  return `https://wa.me/${formatted}`;
};

// WhatsApp icon SVG component
const WhatsAppIcon = () => (
  <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
  </svg>
);

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
      // Fetch all events for calendar view (birthdays need all for month-day matching)
      const response = await api.get('/care-events?limit=2000');
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

    // Add empty slots for days before the first day of the month
    const startDayOfWeek = firstDay.getDay(); // 0 = Sunday, 1 = Monday, etc.
    for (let i = 0; i < startDayOfWeek; i++) {
      days.push(null); // Empty slot
    }

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
            {days.map((day, index) => {
              // Handle empty slots (days before the first of the month)
              if (!day) {
                return <div key={`empty-${index}`} className="border rounded-lg p-2 min-h-[80px] bg-muted/20" />;
              }

              // Use local date string (YYYY-MM-DD) without UTC conversion
              const localDateStr = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
              // For birthdays, match by month-day pattern (birthdays recur annually)
              const monthDay = `-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
              const dayEvents = events.filter(e => {
                if (e.event_type === 'birthday') {
                  // Match birthday by month-day pattern (e.g., -12-25 for Dec 25)
                  return e.event_date && e.event_date.endsWith(monthDay);
                }
                // Other events match by exact date
                return e.event_date === localDateStr;
              });

              // Check if this is today
              const today = new Date();
              const isToday = day.getDate() === today.getDate() &&
                              day.getMonth() === today.getMonth() &&
                              day.getFullYear() === today.getFullYear();

              return (
                <div
                  key={day.toISOString()}
                  className={`border rounded-lg p-2 min-h-[80px] transition-all ${isToday ? 'ring-2 ring-teal-500 bg-teal-50' : ''} ${dayEvents.length > 0 ? 'hover:bg-teal-50 cursor-pointer hover:shadow-md' : 'hover:bg-muted/50'}`}
                  onClick={() => handleDateClick(day, dayEvents)}
                >
                  <div className={`text-sm font-semibold mb-1 ${isToday ? 'text-teal-700' : ''}`}>{day.getDate()}</div>
                  {dayEvents.slice(0, 2).map(e => (
                    <div key={e.id} className="text-xs bg-teal-100 text-teal-700 rounded px-1 mb-1 truncate">
                      {e.event_type === 'birthday' ? '🎂 Birthday' : e.event_type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
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
              {t('events_on')} {selectedDate && selectedDate.toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' })}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {Object.entries(groupEventsByType(selectedDateEvents)).map(([type, typeEvents]) => {
              // Get event type config for styling
              const typeConfig = {
                birthday: { icon: Users, color: 'text-amber-600', bgColor: 'bg-amber-50', btnColor: 'bg-amber-500 hover:bg-amber-600' },
                grief_loss: { icon: Heart, color: 'text-pink-600', bgColor: 'bg-pink-50', btnColor: 'bg-pink-500 hover:bg-pink-600' },
                hospital_visit: { icon: Hospital, color: 'text-blue-600', bgColor: 'bg-blue-50', btnColor: 'bg-blue-500 hover:bg-blue-600' },
                accident_illness: { icon: Hospital, color: 'text-blue-600', bgColor: 'bg-blue-50', btnColor: 'bg-blue-500 hover:bg-blue-600' },
                financial_aid: { icon: DollarSign, color: 'text-green-600', bgColor: 'bg-green-50', btnColor: 'bg-green-500 hover:bg-green-600' }
              };
              const config = typeConfig[type] || { icon: Users, color: 'text-teal-600', bgColor: 'bg-teal-50', btnColor: 'bg-teal-500 hover:bg-teal-600' };
              const IconComponent = config.icon;

              return (
                <Card key={type} className="card-border-left-teal">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <IconComponent className={`w-5 h-5 ${config.color}`} />
                      {t(`event_types.${type}`) || type.replace('_', ' ').toUpperCase()} ({typeEvents.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {typeEvents.map(event => (
                        <div key={event.id} className={`p-4 ${config.bgColor} rounded-lg border ${event.completed ? 'opacity-60' : ''}`}>
                          <div className="flex items-start gap-3">
                            {/* Member avatar */}
                            {event.member_id && event.member_name && (
                              <Link
                                to={`/members/${event.member_id}`}
                                onClick={() => setDetailsOpen(false)}
                                className="flex-shrink-0"
                              >
                                <MemberAvatar
                                  member={{
                                    name: event.member_name,
                                    photo_url: event.member_photo_url
                                  }}
                                  size="md"
                                />
                              </Link>
                            )}
                            <div className="flex-1 min-w-0">
                              {/* Member name as clickable link */}
                              {event.member_id && event.member_name ? (
                                <Link
                                  to={`/members/${event.member_id}`}
                                  className={`font-semibold text-base hover:underline ${config.color}`}
                                  onClick={() => setDetailsOpen(false)}
                                >
                                  {event.member_name}
                                </Link>
                              ) : (
                                <p className="font-semibold text-base">{event.title || 'Unknown'}</p>
                              )}
                              {event.description && (
                                <p className="text-sm text-muted-foreground mt-1">{event.description}</p>
                              )}
                              {/* Show completed status */}
                              {event.completed && (
                                <span className="inline-flex items-center gap-1 text-xs text-green-600 mt-1">
                                  <Check className="w-3 h-3" /> {t('completed')}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Action buttons */}
                          {!event.completed && (
                            <div className="flex gap-2 mt-3">
                              {/* WhatsApp button */}
                              {event.member_phone && event.member_phone !== 'null' && event.member_phone !== 'NULL' && (
                                <Button
                                  size="sm"
                                  className={`${config.btnColor} text-white flex-1`}
                                  asChild
                                >
                                  <a
                                    href={formatPhoneForWhatsApp(event.member_phone)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-center gap-1"
                                  >
                                    <WhatsAppIcon />
                                    <span>WhatsApp</span>
                                  </a>
                                </Button>
                              )}

                              {/* Mark Complete button */}
                              <Button
                                size="sm"
                                variant="outline"
                                className="flex-1"
                                onClick={async () => {
                                  try {
                                    // Use the appropriate endpoint based on event type
                                    if (type === 'grief_loss' && event.grief_stage_id) {
                                      await api.post(`/grief-support/${event.grief_stage_id}/complete`);
                                    } else {
                                      await api.post(`/care-events/${event.id}/complete`);
                                    }
                                    toast.success(t('toasts.event_marked_completed'));
                                    // Update local state to show as completed
                                    setSelectedDateEvents(prev =>
                                      prev.map(e => e.id === event.id ? {...e, completed: true} : e)
                                    );
                                    // Refresh events list
                                    loadEvents();
                                  } catch (error) {
                                    toast.error(t('toasts.failed_mark_completed'));
                                  }
                                }}
                              >
                                <Check className="w-4 h-4 mr-1" />
                                {t('mark_complete')}
                              </Button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Calendar;