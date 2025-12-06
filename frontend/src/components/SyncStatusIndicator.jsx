/**
 * SyncStatusIndicator - Shows offline queue and sync status
 *
 * Displays a subtle indicator showing:
 * - Online/offline status
 * - Pending operations count
 * - Sync in progress animation
 */
import { Wifi, WifiOff, RefreshCw, CloudOff, Check } from 'lucide-react';

import { useOfflineSync } from '@/hooks/useOfflineSync';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function SyncStatusIndicator({ className }) {
  const { isOnline, isSyncing, pendingCount, sync, stats } = useOfflineSync();

  // Don't show anything if online with no pending operations
  if (isOnline && pendingCount === 0 && !isSyncing) {
    return null;
  }

  const getTitle = () => {
    if (!isOnline) return 'Offline - changes will sync when connected';
    if (isSyncing) return 'Syncing pending changes...';
    if (pendingCount > 0) return `${pendingCount} pending changes - tap to sync`;
    return 'All changes synced';
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={isOnline && pendingCount > 0 && !isSyncing ? sync : undefined}
      disabled={!isOnline || isSyncing || pendingCount === 0}
      title={getTitle()}
      className={cn(
        'relative px-2 h-8',
        !isOnline && 'text-amber-600',
        isSyncing && 'animate-pulse',
        className
      )}
    >
      {/* Icon */}
      {!isOnline ? (
        <WifiOff className="h-4 w-4" />
      ) : isSyncing ? (
        <RefreshCw className="h-4 w-4 animate-spin" />
      ) : pendingCount > 0 ? (
        <CloudOff className="h-4 w-4" />
      ) : (
        <Check className="h-4 w-4 text-green-600" />
      )}

      {/* Badge for pending count */}
      {pendingCount > 0 && (
        <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white">
          {pendingCount > 9 ? '9+' : pendingCount}
        </span>
      )}
    </Button>
  );
}

export default SyncStatusIndicator;
