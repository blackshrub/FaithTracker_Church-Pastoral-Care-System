/**
 * BulkActionBar - Floating action bar for bulk operations
 *
 * Appears when items are selected, provides bulk complete/ignore/delete actions.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X, Trash2, XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function BulkActionBar({
  selectedCount,
  onComplete,
  onIgnore,
  onDelete,
  onClear,
  isLoading,
  className,
}) {
  const { t } = useTranslation();

  if (selectedCount === 0) return null;

  return (
    <div
      className={cn(
        'fixed bottom-20 left-1/2 -translate-x-1/2 z-50',
        'bg-white rounded-full shadow-lg border border-gray-200',
        'px-4 py-2 flex items-center gap-2',
        'animate-in slide-in-from-bottom-4 duration-300',
        className
      )}
    >
      <span className="text-sm font-medium text-gray-700 px-2">
        {t('bulk.selected', { count: selectedCount })}
      </span>

      <div className="h-6 w-px bg-gray-200" />

      <Button
        size="sm"
        variant="ghost"
        onClick={onComplete}
        disabled={isLoading}
        className="text-green-600 hover:text-green-700 hover:bg-green-50"
      >
        <Check className="h-4 w-4 mr-1" />
        {t('bulk.complete_all', 'Complete')}
      </Button>

      <Button
        size="sm"
        variant="ghost"
        onClick={onIgnore}
        disabled={isLoading}
        className="text-gray-600 hover:text-gray-700 hover:bg-gray-100"
      >
        <X className="h-4 w-4 mr-1" />
        {t('bulk.ignore_all', 'Ignore')}
      </Button>

      <Button
        size="sm"
        variant="ghost"
        onClick={onDelete}
        disabled={isLoading}
        className="text-red-600 hover:text-red-700 hover:bg-red-50"
      >
        <Trash2 className="h-4 w-4 mr-1" />
        {t('bulk.delete_all', 'Delete')}
      </Button>

      <div className="h-6 w-px bg-gray-200" />

      <Button
        size="sm"
        variant="ghost"
        onClick={onClear}
        disabled={isLoading}
        className="text-gray-500 hover:text-gray-600"
      >
        <XCircle className="h-4 w-4" />
      </Button>
    </div>
  );
}

export default BulkActionBar;
