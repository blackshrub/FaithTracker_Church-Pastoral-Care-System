import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LanguageToggle } from './LanguageToggle';
import { MobileBottomNav } from './MobileBottomNav';
import { DesktopSidebar } from './DesktopSidebar';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { Church, LogOut, ChevronDown } from 'lucide-react';

export const Layout = ({ children }) => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  
  return (
    <div className="flex min-h-screen">
      {/* Desktop Sidebar - Hidden on mobile */}
      <DesktopSidebar />
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Top Header - Responsive */}
        <header className="bg-white border-b border-border sticky top-0 z-40 sm:hidden">
          <div className="container mx-auto px-4">
            <div className="flex items-center justify-between h-14">
              {/* Logo */}
              <Link to="/dashboard" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center">
                  <Church className="w-5 h-5 text-white" />
                </div>
                <span className="text-lg font-playfair font-bold text-teal-700">FaithTracker</span>
              </Link>
              
              {/* Right Side - User Menu & Language */}
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="gap-1 hover:bg-teal-50">
                      <div className="w-7 h-7 bg-teal-100 rounded-full flex items-center justify-center">
                        <span className="text-xs font-semibold text-teal-700">
                          {user?.name?.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <ChevronDown className="w-3 h-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <div className="px-2 py-2 border-b">
                      <p className="text-sm font-semibold text-gray-700">{user?.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {user?.role === 'full_admin' ? t('full_admin') : 
                         user?.role === 'campus_admin' ? t('campus_admin') : t('pastor')}
                      </p>
                    </div>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem 
                      onClick={() => { logout(); navigate('/login'); }} 
                      className="text-red-600"
                    >
                      <LogOut className="w-4 h-4 mr-2" />
                      {t('logout')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <LanguageToggle />
              </div>
            </div>
          </div>
        </header>
        
        {/* Desktop Header - Hidden on mobile */}
        <header className="hidden sm:block bg-white border-b border-border sticky top-0 z-40">
          <div className="px-6">
            <div className="flex items-center justify-end h-16 gap-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="gap-2 hover:bg-teal-50">
                    <div className="text-right">
                      <p className="text-sm font-semibold text-gray-700">{user?.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {user?.role === 'full_admin' ? t('full_admin') : 
                         user?.role === 'campus_admin' ? t('campus_admin') : t('pastor')}
                      </p>
                    </div>
                    <ChevronDown className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuSeparator />
                  <DropdownMenuItem 
                    onClick={() => { logout(); navigate('/login'); }} 
                    className="text-red-600"
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    {t('logout')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <LanguageToggle />
            </div>
          </div>
        </header>
        
        {/* Main Content with page animation */}
        <main className="flex-1 container mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 page-enter">
          {children}
        </main>
      </div>
      
      {/* Mobile Bottom Navigation */}
      <MobileBottomNav />
    </div>
  );
};

export default Layout;