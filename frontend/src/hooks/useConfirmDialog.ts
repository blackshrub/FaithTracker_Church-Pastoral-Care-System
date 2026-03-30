/**
 * useConfirmDialog Hook
 * Reusable confirmation dialog state management
 * Eliminates duplicate confirm dialog patterns across 5+ pages
 */

import { useState, useCallback } from 'react';

export type ConfirmDialogVariant = 'default' | 'destructive';

export interface ConfirmDialogState {
  open: boolean;
  title: string;
  description: string;
  onConfirm: () => void;
  variant: ConfirmDialogVariant;
}

export interface UseConfirmDialogReturn {
  confirmDialog: ConfirmDialogState;
  showConfirm: (title: string, description: string, onConfirm: () => void, variant?: ConfirmDialogVariant) => void;
  closeConfirm: () => void;
}

export const useConfirmDialog = (): UseConfirmDialogReturn => {
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    title: '',
    description: '',
    onConfirm: () => {},
    variant: 'default'
  });

  const showConfirm = useCallback((title: string, description: string, onConfirm: () => void, variant: ConfirmDialogVariant = 'default') => {
    setConfirmDialog({ open: true, title, description, onConfirm, variant });
  }, []);

  const closeConfirm = useCallback(() => {
    setConfirmDialog({
      open: false,
      title: '',
      description: '',
      onConfirm: () => {},
      variant: 'default'
    });
  }, []);

  return {
    confirmDialog,
    showConfirm,
    closeConfirm
  };
};

export default useConfirmDialog;
