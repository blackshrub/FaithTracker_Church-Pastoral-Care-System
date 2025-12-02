import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Home,
  Users,
  Calendar,
  BarChart3,
  DollarSign,
  Settings,
  Shield,
  Upload,
  MessageSquare,
  Bell,
  Church,
  Activity,
  FileText
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export const DesktopSidebar = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const location = useLocation();
  
  const mainNavigation = [
    { name: t('dashboard'), href: '/dashboard', icon: Home, testId: 'sidebar-dashboard' },
    { name: t('members'), href: '/members', icon: Users, testId: 'sidebar-members' },
    { name: t('calendar'), href: '/calendar', icon: Calendar, testId: 'sidebar-calendar' },
    { name: t('financial_aid'), href: '/financial-aid', icon: DollarSign, testId: 'sidebar-financial-aid' },
    { name: t('analytics'), href: '/analytics', icon: BarChart3, testId: 'sidebar-analytics' },
    { name: t('reports.title') || 'Reports', href: '/reports', icon: FileText, testId: 'sidebar-reports' },
  ];
  
  const adminNavigation = [
    ...(user?.role === 'full_admin' ? [{ 
      name: t('admin_dashboard'), 
      href: '/admin', 
      icon: Shield, 
      testId: 'sidebar-admin' 
    }] : []),
    { name: t('activity_log'), href: '/activity-log', icon: Activity, testId: 'sidebar-activity-log' },
    { name: t('import_export'), href: '/import-export', icon: Upload, testId: 'sidebar-import-export' },
    { name: t('messaging'), href: '/messaging', icon: MessageSquare, testId: 'sidebar-messaging' },
    { name: t('whatsapp_logs'), href: '/whatsapp-logs', icon: Bell, testId: 'sidebar-whatsapp-logs' },
    { name: t('settings'), href: '/settings', icon: Settings, testId: 'sidebar-settings' },
  ];
  
  const isActive = (href) => {
    if (href === '/dashboard') {
      return location.pathname === '/' || location.pathname === '/dashboard';
    }
    return location.pathname === href;
  };
  
  return (
    <aside
      className="hidden sm:flex flex-col w-64 bg-card border-r border-border h-screen sticky top-0"
      data-testid="desktop-sidebar"
    >
      {/* Logo/Header */}
      <div className="p-6 border-b border-border">
        <Link to="/dashboard" className="flex items-center gap-3">
          <div className="w-10 h-10 bg-teal-500 rounded-lg flex items-center justify-center">
            <Church className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-h3 text-teal-700 dark:text-teal-400 leading-tight">{t('components.app_name')}</h2>
            <p className="text-xs text-muted-foreground">{t('pastoral_care')}</p>
          </div>
        </Link>
      </div>
      
      {/* Main Navigation */}
      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        <div className="space-y-1">
          {mainNavigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            
            return (
              <Link key={item.name} to={item.href}>
                <Button
                  variant="ghost"
                  className={
                    `w-full justify-start h-12 transition-all duration-200 ${
                      active
                        ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-400 font-semibold'
                        : 'text-foreground/70 hover:bg-teal-50 dark:hover:bg-teal-900/20 hover:text-teal-700 dark:hover:text-teal-400'
                    }`
                  }
                  data-testid={item.testId}
                >
                  <Icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Button>
              </Link>
            );
          })}
        </div>

        <Separator className="my-4" />

        {/* Admin/Settings Navigation */}
        <div className="space-y-1">
          <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            {t('administration')}
          </p>
          {adminNavigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link key={item.name} to={item.href}>
                <Button
                  variant="ghost"
                  className={
                    `w-full justify-start h-12 transition-all duration-200 ${
                      active
                        ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-400 font-semibold'
                        : 'text-foreground/70 hover:bg-teal-50 dark:hover:bg-teal-900/20 hover:text-teal-700 dark:hover:text-teal-400'
                    }`
                  }
                  data-testid={item.testId}
                >
                  <Icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Button>
              </Link>
            );
          })}
        </div>
      </nav>
      
      {/* User Info at Bottom */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-teal-100 dark:bg-teal-900 rounded-full flex items-center justify-center">
            <span className="text-sm font-semibold text-teal-700 dark:text-teal-300">
              {user?.name?.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{user?.name}</p>
            <p className="text-xs text-muted-foreground truncate">
              {user?.role === 'full_admin' ? t('full_admin') :
               user?.role === 'campus_admin' ? t('campus_admin') : t('pastor')}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default DesktopSidebar;
