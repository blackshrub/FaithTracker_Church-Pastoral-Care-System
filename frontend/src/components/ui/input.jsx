import * as React from 'react';

import { cn } from '@/lib/utils';

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  // Auto-set inputMode for better mobile keyboard
  const inputMode = props.inputMode || getInputMode(type);

  return (
    <input
      type={type}
      inputMode={inputMode}
      className={cn(
        // h-11 (44px) for HIG-compliant touch targets
        // text-base prevents iOS zoom on focus (16px minimum)
        'flex h-11 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
        // Error state styling
        props['aria-invalid'] && 'border-destructive focus-visible:ring-destructive',
        className
      )}
      ref={ref}
      {...props}
    />
  );
});

// Helper to auto-detect inputMode from type
function getInputMode(type) {
  switch (type) {
    case 'email':
      return 'email';
    case 'tel':
      return 'tel';
    case 'url':
      return 'url';
    case 'number':
      return 'decimal';
    case 'search':
      return 'search';
    default:
      return undefined;
  }
}
Input.displayName = 'Input';

export { Input };
