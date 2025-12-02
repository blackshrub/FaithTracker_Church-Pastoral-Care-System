import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import LazyImage from '@/components/LazyImage';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

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
  
  // Handle both absolute URLs (from external CDN) and relative paths (local uploads)
  const photoUrl = member.photo_url
    ? (member.photo_url.startsWith('http') ? member.photo_url : `${BACKEND_URL}${member.photo_url}`)
    : null;
  
  return (
    <Avatar className={sizeClasses[size]} data-testid="member-avatar">
      {photoUrl ? (
        <LazyImage 
          src={photoUrl} 
          alt={member.name}
          className="w-full h-full rounded-full object-cover"
          placeholderClassName="w-full h-full rounded-full bg-teal-100 flex items-center justify-center"
          onError={() => {
            // Show initials fallback on error
          }}
        />
      ) : (
        <AvatarFallback className="bg-teal-100 text-teal-700 font-semibold">
          {getInitials(member.name)}
        </AvatarFallback>
      )}
    </Avatar>
  );
};