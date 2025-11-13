import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const MemberAvatar = ({ member, size = 'md' }) => {
  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-12 h-12 text-sm',
    lg: 'w-20 h-20 text-lg',
    xl: 'w-32 h-32 text-2xl'
  };
  
  const getInitials = (name) => {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return parts[0][0] + parts[parts.length - 1][0];
    }
    return name.substring(0, 2);
  };
  
  const photoUrl = member.photo_url ? `${BACKEND_URL}/api${member.photo_url}` : null;
  
  return (
    <Avatar className={sizeClasses[size]} data-testid="member-avatar">
      {photoUrl && <AvatarImage src={photoUrl} alt={member.name} className="object-cover" />}
      <AvatarFallback className="bg-primary-100 text-primary-700 font-semibold">
        {getInitials(member.name)}
      </AvatarFallback>
    </Avatar>
  );
};