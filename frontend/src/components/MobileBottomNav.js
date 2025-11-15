import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Home, Users, Calendar, BarChart3, MoreHorizontal, DollarSign, Shield, Upload, MessageSquare, Bell, Settings as SettingsIcon, X } from 'lucide-react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/context/AuthContext';

export const MobileBottomNav = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  
  const navigation = [
    {
      name: t('dashboard'),
      href: '/dashboard',
      icon: Home,
      testId: 'nav-dashboard'
    },
    {
      name: t('members'),
      href: '/members',
      icon: Users,
      testId: 'nav-members'
    },
    {
      name: t('calendar'),
      href: '/calendar',
      icon: Calendar,
      testId: 'nav-calendar'
    },
    {
      name: t('analytics'),
      href: '/analytics',
      icon: BarChart3,
      testId: 'nav-analytics'
    }
  ];
  
  const moreMenuItems = [
    { name: t('financial_aid'), href: '/financial-aid', icon: DollarSign },
    ...(user?.role === 'full_admin' ? [{ name: t('admin_dashboard'), href: '/admin', icon: Shield }] : []),
    { name: t('import_export'), href: '/import-export', icon: Upload },
    { name: t('messaging'), href: '/messaging', icon: MessageSquare },
    { name: t('whatsapp_logs'), href: '/whatsapp-logs', icon: Bell },
    { name: t('settings'), href: '/settings', icon: SettingsIcon }
  ];
  
  const isActive = (href) => {
    if (href === '/dashboard') {
      return location.pathname === '/' || location.pathname === '/dashboard';
    }
    return location.pathname === href;
  };
  
  const handleMoreMenuClick = (href) => {
    navigate(href);
    setMoreMenuOpen(false);
  };
  
  return (
    <>
      <nav 
        className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 sm:hidden"
        data-testid="mobile-bottom-nav"
      >
        <div className="grid grid-cols-5 h-16">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            
            return (
              <Link
                key={item.name}
                to={item.href}
                className={
                  `flex flex-col items-center justify-center gap-1 transition-colors duration-200 ${
                    active 
                      ? 'text-teal-600' 
                      : 'text-gray-600 hover:text-teal-500'
                  }`
                }
                data-testid={item.testId}
              >
                <Icon className="h-5 w-5" />
                <span className="text-xs font-medium">{item.name}</span>
              </Link>
            );
          })}
          
          {/* More Menu Trigger */}
          <Sheet open={moreMenuOpen} onOpenChange={setMoreMenuOpen}>
            <SheetTrigger asChild>
              <button
                className="flex flex-col items-center justify-center gap-1 transition-colors duration-200 text-gray-600 hover:text-teal-500"
                data-testid="nav-more"
              >
                <MoreHorizontal className="h-5 w-5" />
                <span className="text-xs font-medium">{t('more')}</span>
              </button>
            </SheetTrigger>
            <SheetContent side="bottom" className="h-[80vh] rounded-t-2xl">
              <SheetHeader className="mb-4">
                <SheetTitle className="text-2xl font-playfair">{t('more_menu')}</SheetTitle>
              </SheetHeader>
              
              <div className="space-y-2">
                {moreMenuItems.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  
                  return (
                    <button
                      key={item.name}
                      onClick={() => handleMoreMenuClick(item.href)}
                      className={`w-full flex items-center gap-4 p-4 rounded-lg transition-colors ${
                        active
                          ? 'bg-teal-50 text-teal-700 font-semibold'
                          : 'text-gray-700 hover:bg-teal-50 hover:text-teal-700'
                      }`}
                    >
                      <Icon className="h-6 w-6" />
                      <span className="text-base">{item.name}</span>
                    </button>
                  );
                })}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </nav>
    </>
  );
};

export default MobileBottomNav;
