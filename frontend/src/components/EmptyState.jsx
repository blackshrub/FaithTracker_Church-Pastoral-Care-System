/**
 * EmptyState - Displays when no data is available
 * Provides helpful messaging and optional action button
 */

import { Button } from '@/components/ui/button';
import {
  Users,
  Calendar,
  Search,
  FileText,
  Heart,
  Inbox
} from 'lucide-react';

const icons = {
  members: Users,
  events: Calendar,
  search: Search,
  documents: FileText,
  care: Heart,
  default: Inbox
};

export function EmptyState({
  icon = 'default',
  title = 'No data found',
  description = 'There is nothing to display here yet.',
  actionLabel,
  onAction,
  className = ''
}) {
  const IconComponent = icons[icon] || icons.default;

  return (
    <div className={`flex flex-col items-center justify-center py-12 px-4 text-center animate-fade-in ${className}`}>
      <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
        <IconComponent className="w-8 h-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">
        {title}
      </h3>
      <p className="text-sm text-muted-foreground max-w-sm mb-6">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button onClick={onAction} variant="outline">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

// Pre-configured empty states for common scenarios
export function EmptyMembers({ onAddMember }) {
  return (
    <EmptyState
      icon="members"
      title="No members yet"
      description="Start building your congregation by adding your first member."
      actionLabel="Add Member"
      onAction={onAddMember}
    />
  );
}

export function EmptySearch({ searchTerm }) {
  return (
    <EmptyState
      icon="search"
      title="No results found"
      description={`We couldn't find any matches for "${searchTerm}". Try adjusting your search terms.`}
    />
  );
}

export function EmptyTasks() {
  return (
    <EmptyState
      icon="care"
      title="All caught up!"
      description="You have no pending tasks. Great job staying on top of pastoral care!"
    />
  );
}

export function EmptyEvents() {
  return (
    <EmptyState
      icon="events"
      title="No upcoming events"
      description="There are no scheduled events for this period."
    />
  );
}

export default EmptyState;
