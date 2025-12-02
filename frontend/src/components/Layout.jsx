import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LanguageToggle } from './LanguageToggle';
import { ThemeToggle } from './ThemeToggle';
import { MobileBottomNav } from './MobileBottomNav';
import { DesktopSidebar } from './DesktopSidebar';
import SearchBar from './SearchBar';
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
        <header className="bg-card border-b border-border sticky top-0 z-40 sm:hidden">
          <div className="container mx-auto px-4">
            <div className="flex items-center justify-between h-14">
              {/* Logo */}
              <Link to="/dashboard" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center">
                  <Church className="w-5 h-5 text-white" />
                </div>
                <span className="text-lg font-playfair font-bold text-teal-700 dark:text-teal-400">{t('components.app_name')}</span>
              </Link>

              {/* Right Side - User Info & Language */}
              <div className="flex items-center gap-1">
                {/* User Info Display - No Dropdown on Mobile */}
                <div className="flex items-center gap-2">
                  {user?.photo_url ? (
                    <img
                      src={user.photo_url.startsWith('http') ? user.photo_url : `${import.meta.env.VITE_BACKEND_URL}${user.photo_url}`}
                      alt={user.name}
                      className="w-7 h-7 rounded-full object-cover border border-teal-200 dark:border-teal-700"
                    />
                  ) : (
                    <div className="w-7 h-7 bg-teal-100 dark:bg-teal-900 rounded-full flex items-center justify-center">
                      <span className="text-xs font-semibold text-teal-700 dark:text-teal-300">
                        {user?.name?.charAt(0).toUpperCase()}
                      </span>
                    </div>
                  )}
                </div>
                <ThemeToggle />
                <LanguageToggle />
              </div>
            </div>
            {/* Search Bar - Mobile (Full width below header) */}
            <div className="pb-3">
              <SearchBar />
            </div>
          </div>
        </header>
        
        {/* Desktop Header - Hidden on mobile */}
        <header className="hidden sm:block bg-card border-b border-border sticky top-0 z-40">
          <div className="px-6">
            <div className="flex items-center justify-between h-16 gap-4">
              {/* Search Bar - Desktop (flex-1 for expansion) */}
              <div className="flex-1 max-w-2xl">
                <SearchBar />
              </div>

              {/* Right Side - User & Language */}
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="gap-2 hover:bg-teal-50 dark:hover:bg-teal-900/30">
                      <div className="text-right">
                        <p className="text-sm font-semibold text-foreground">{user?.name}</p>
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
                      className="text-red-600 dark:text-red-400"
                    >
                      <LogOut className="w-4 h-4 mr-2" />
                      {t('logout')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <ThemeToggle />
                <LanguageToggle />
              </div>
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