import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LanguageToggle } from './LanguageToggle';
import { Button } from '@/components/ui/button';
import { Church, LayoutDashboard, Users, DollarSign, BarChart3, Settings, Upload, Cog, LogOut, Shield, MessageSquare } from 'lucide-react';

export const Layout = ({ children }) => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Members', href: '/members', icon: Users },
    { name: 'Financial Aid', href: '/financial-aid', icon: DollarSign },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Import/Export', href: '/import-export', icon: Upload },
    { name: 'Settings', href: '/settings', icon: Cog },
  ];
  
  if (user?.role === 'full_admin') {
    navigation.splice(5, 0, { name: 'Admin', href: '/admin', icon: Shield });
  }
  
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
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.name} to={item.href}>
                    <Button
                      variant="ghost"
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
              {user?.role === 'full_admin' && (
                <Link to="/admin">
                  <Button
                    variant="ghost"
                    className={isActive('/admin') ? 'text-teal-700 bg-teal-50 font-semibold' : 'text-gray-600 hover:text-teal-700 hover:bg-teal-50'}
                  >
                    <Shield className="w-4 h-4 mr-2" />
                    Admin
                  </Button>
                </Link>
              )}
            </nav>
            
            {/* Right Side */}
            <div className="flex items-center gap-3">
              <div className="text-right hidden md:block">
                <p className="text-sm font-semibold">{user?.name}</p>
                <p className="text-xs text-muted-foreground">Staff</p>
              </div>
              <LanguageToggle />
              <Button variant="outline" size="sm" onClick={() => { logout(); navigate('/login'); }}>
                <LogOut className="w-4 h-4" />
              </Button>
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