import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LanguageToggle } from './LanguageToggle';
import { Button } from '@/components/ui/button';
import { 
  LayoutDashboard, 
  Users, 
  Heart, 
  DollarSign, 
  BarChart3,
  Settings,
  Menu,
  X,
  LogOut,
  UserCircle
} from 'lucide-react';

export const Layout = ({ children }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  const navigation = [
    { name: t('dashboard'), href: '/dashboard', icon: LayoutDashboard },
    { name: t('members'), href: '/members', icon: Users },
    { name: t('financial_aid'), href: '/financial-aid', icon: DollarSign },
    { name: t('analytics'), href: '/analytics', icon: BarChart3 },
    { name: t('integrations'), href: '/integrations', icon: Settings },
  ];
  
  const isActive = (href) => {
    if (href === '/dashboard') return location.pathname === '/' || location.pathname === '/dashboard';
    return location.pathname.startsWith(href);
  };
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-card backdrop-blur supports-[backdrop-filter]:bg-card/95">
        <div className="container flex h-16 items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              data-testid="mobile-menu-toggle"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
            
            <Link to="/" className="flex items-center gap-2" data-testid="app-logo">
              <Heart className="h-6 w-6 text-primary-500" fill="currentColor" />
              <span className="font-manrope font-bold text-lg text-foreground">
                {t('app_title')}
              </span>
            </Link>
          </div>
          
          <div className="flex items-center gap-2">
            <LanguageToggle />
          </div>
        </div>
        
        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div className="border-t border-border bg-card md:hidden">
            <nav className="container px-4 py-4 space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                      isActive(item.href)
                        ? 'bg-primary-50 text-primary-700 font-medium'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    }`}
                    data-testid={`mobile-nav-${item.href}`}
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
        )}
      </header>
      
      {/* Desktop Navigation */}
      <div className="container px-4 md:px-6 mt-6">
        <nav className="hidden md:flex items-center gap-2 mb-6 flex-wrap">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.name} to={item.href}>
                <Button
                  variant={isActive(item.href) ? 'default' : 'ghost'}
                  size="sm"
                  className={isActive(item.href) 
                    ? 'bg-primary-100 text-primary-700 font-semibold hover:bg-primary-200 border border-primary-300' 
                    : 'text-foreground hover:bg-muted hover:text-foreground'
                  }
                  data-testid={`nav-${item.href}`}
                >
                  <Icon className="h-4 w-4 mr-2" />
                  {item.name}
                </Button>
              </Link>
            );
          })}
        </nav>
      </div>
      
      {/* Main Content */}
      <main className="container px-4 md:px-6 pb-12">
        {children}
      </main>
    </div>
  );
};