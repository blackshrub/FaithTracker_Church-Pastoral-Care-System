import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

import { Button } from '@/components/ui/button';

export const LanguageToggle = () => {
  const { i18n } = useTranslation();
  const [currentLang, setCurrentLang] = useState(i18n.language);
  
  useEffect(() => {
    // Update local state when language changes
    const handleLanguageChange = (lng) => {
      setCurrentLang(lng);
    };
    
    i18n.on('languageChanged', handleLanguageChange);
    
    return () => {
      i18n.off('languageChanged', handleLanguageChange);
    };
  }, [i18n]);
  
  const toggleLanguage = async () => {
    const newLang = currentLang === 'id' ? 'en' : 'id';
    await i18n.changeLanguage(newLang);
    localStorage.setItem('language', newLang);
    setCurrentLang(newLang);
  };
  
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleLanguage}
      className="gap-2"
      data-testid="language-toggle"
    >
      <Globe className="w-4 h-4" />
      <span className="text-sm font-medium">
        {currentLang === 'id' ? '🇮🇩 ID' : '🇬🇧 EN'}
      </span>
    </Button>
  );
};