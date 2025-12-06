import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import LazyImage from '@/components/LazyImage';
import { cn } from '@/lib/utils';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

/**
 * MemberAvatar - Avatar component with View Transitions API support
 *
 * @param {object} member - Member object with name and photo_url
 * @param {string} size - Size variant: 'sm' | 'md' | 'lg' | 'xl'
 * @param {string} className - Additional CSS classes
 * @param {boolean} enableTransition - Enable shared element transition (default: false)
 *
 * When enableTransition is true and member.id is provided, the avatar will
 * morph smoothly between list and detail views using the View Transitions API.
 */
export const MemberAvatar = ({ member, size = 'md', className, enableTransition = false }) => {
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

  // Dynamic view-transition-name for shared element transitions
  // Each member gets a unique transition name based on their ID
  const transitionStyle = enableTransition && member.id
    ? { viewTransitionName: `member-avatar-${member.id}` }
    : undefined;

  return (
    <Avatar
      className={cn(sizeClasses[size], className)}
      style={transitionStyle}
      data-testid="member-avatar"
    >
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