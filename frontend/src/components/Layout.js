import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LanguageToggle } from './LanguageToggle';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { Church, LayoutDashboard, Users, DollarSign, BarChart3, Settings, Upload, Cog, LogOut, Shield, MessageSquare, Calendar as CalIcon, Bell, ChevronDown, Menu, X } from 'lucide-react';

export const Layout = ({ children }) => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  const mainNavigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Members', href: '/members', icon: Users },
    { name: 'Financial Aid', href: '/financial-aid', icon: DollarSign },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Calendar', href: '/calendar', icon: CalIcon },
    { name: 'Messaging', href: '/messaging', icon: MessageSquare },
    { name: 'WhatsApp Logs', href: '/whatsapp-logs', icon: Bell },
  ];
  
  const isActive = (href) => location.pathname === href || (href === '/dashboard' && location.pathname === '/');
  
  return (
    <div className="min-h-screen">
      {/* Top Navigation Bar */}
      <header className="bg-white border-b border-border sticky top-0 z-50">
        <div className="container mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/dashboard" className="flex items-center gap-3">
              <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center">
                <Church className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-playfair font-bold text-teal-700">Pastoral Care</span>
            </Link>
            
            {/* Navigation Links */}
            <nav className="hidden md:flex items-center gap-1">
              {mainNavigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.name} to={item.href}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={isActive(item.href) 
                        ? 'text-teal-700 bg-teal-50 font-semibold' 
                        : 'text-gray-600 hover:text-teal-700 hover:bg-teal-50'
                      }
                    >
                      <Icon className="w-4 h-4 mr-2" />
                      {item.name}
                    </Button>
                  </Link>
                );
              })}
            </nav>
            
            {/* Right Side with Dropdown Menu */}
            <div className="flex items-center gap-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-2">
                    <div className="text-left hidden md:block">
                      <p className="text-sm font-semibold">{user?.name}</p>
                      <p className="text-xs text-muted-foreground">{user?.role === 'full_admin' ? 'Full Admin' : user?.role === 'campus_admin' ? 'Campus Admin' : 'Pastor'}</p>
                    </div>
                    <ChevronDown className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  {user?.role === 'full_admin' && (
                    <>
                      <DropdownMenuItem onClick={() => navigate('/admin')}>
                        <Shield className="w-4 h-4 mr-2" />
                        Admin Dashboard
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  <DropdownMenuItem onClick={() => navigate('/import-export')}>
                    <Upload className="w-4 h-4 mr-2" />
                    Import/Export
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/settings')}>
                    <Cog className="w-4 h-4 mr-2" />
                    Settings
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => { logout(); navigate('/login'); }} className="text-red-600">
                    <LogOut className="w-4 h-4 mr-2" />
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <LanguageToggle />
            </div>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;