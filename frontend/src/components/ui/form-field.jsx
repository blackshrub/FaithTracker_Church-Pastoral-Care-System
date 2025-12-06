import * as React from "react"
import { AlertCircle, CheckCircle2 } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * FormField - Wrapper component for form inputs with validation feedback
 *
 * Provides:
 * - Label with required indicator
 * - Error message display with icon
 * - Success state indicator
 * - Accessible aria attributes
 * - Helper text support
 */
const FormField = React.forwardRef(({
  className,
  label,
  error,
  success,
  helperText,
  required,
  children,
  id,
  ...props
}, ref) => {
  const generatedId = React.useId();
  const fieldId = id || generatedId;
  const errorId = `${fieldId}-error`;
  const helperId = `${fieldId}-helper`;

  // Clone children to inject aria attributes
  const enhancedChildren = React.Children.map(children, child => {
    if (React.isValidElement(child)) {
      return React.cloneElement(child, {
        id: fieldId,
        'aria-invalid': !!error,
        'aria-describedby': cn(
          error && errorId,
          helperText && helperId
        ) || undefined,
        'aria-required': required,
      });
    }
    return child;
  });

  return (
    <div className={cn("space-y-2", className)} ref={ref} {...props}>
      {label && (
        <label
          htmlFor={fieldId}
          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        >
          {label}
          {required && (
            <span className="text-destructive ml-1" aria-hidden="true">*</span>
          )}
        </label>
      )}

      <div className="relative">
        {enhancedChildren}

        {/* Success indicator */}
        {success && !error && (
          <CheckCircle2
            className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-green-500 pointer-events-none"
            aria-hidden="true"
          />
        )}
      </div>

      {/* Error message with animation */}
      {error && (
        <div
          id={errorId}
          className="flex items-center gap-1.5 text-sm text-destructive animate-fade-in"
          role="alert"
          aria-live="polite"
        >
          <AlertCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* Helper text */}
      {helperText && !error && (
        <p
          id={helperId}
          className="text-sm text-muted-foreground"
        >
          {helperText}
        </p>
      )}
    </div>
  );
});

FormField.displayName = "FormField"

export { FormField }
